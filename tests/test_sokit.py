"""Checks that run without a robot, on Windows, Linux and macOS:  python -m unittest discover -s tests -v

They cover the parts of `so` that differ between operating systems (command quoting, paths,
sleep prevention, dataset lookup) and the files other steps rely on (config, recording list).
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sokit import cloud, config, demo, ports, runner, sensecraft  # noqa: E402


class CommandFormatting(unittest.TestCase):
    ARGV = ["lerobot-record", "--dataset.single_task=Put the battery in the bin", "--robot.port=/dev/ttyACM0"]

    def test_bash_style_quotes_spaces_and_continues_with_backslash(self):
        out = runner.format_cmd(self.ARGV, "bash")
        self.assertIn("'--dataset.single_task=Put the battery in the bin'", out)
        self.assertIn(" \\\n  ", out)

    def test_powershell_and_cmd_styles(self):
        self.assertIn(" `\n  ", runner.format_cmd(self.ARGV, "powershell"))
        self.assertIn(" ^\n  ", runner.format_cmd(self.ARGV, "cmd"))

    def test_launcher_extension_is_hidden(self):
        self.assertTrue(runner.format_cmd(["C:/env/Scripts/lerobot-train.exe", "--steps=1"], "bash").startswith("lerobot-train"))

    def test_default_style_matches_the_platform(self):
        if os.name != "nt":
            self.assertEqual(runner.shell_style(), "bash")


class PlatformHelpers(unittest.TestCase):
    def test_wsl_detection_returns_a_bool(self):
        self.assertIsInstance(runner.is_wsl(), bool)
        if os.name == "nt" or sys.platform == "darwin":
            self.assertFalse(runner.is_wsl())

    def test_keep_awake_never_raises(self):
        cmd = runner.keep_awake_command()
        self.assertTrue(cmd is None or (isinstance(cmd, list) and shutil.which(cmd[0])))
        with runner.KeepAwake():
            pass

    def test_missing_port_hint_names_this_system(self):
        hint = ports._missing_port_hint()
        expected = "Windows" if os.name == "nt" else ("macOS" if sys.platform == "darwin" else "Linux")
        self.assertIn(expected, hint)

    def test_env_path_fixup_is_harmless(self):
        runner.ensure_env_on_path()
        self.assertIn("PYTHONUTF8", runner.child_env())


class Config(unittest.TestCase):
    def test_repo_config_loads(self):
        cfg = config.load_config()
        self.assertNotEqual(cfg["robot"]["id"], cfg["teleop"]["id"])
        self.assertTrue(cfg["task"]["description"])
        self.assertGreaterEqual(len(cfg["cameras"]), 1)

    def test_cameras_argument_shape(self):
        cfg = {"cameras": {"top": {"index_or_path": 1, "width": 640, "height": 480, "fps": 30},
                           "wrist": {"index_or_path": "/dev/video2", "width": 640, "height": 480, "fps": 30}}}
        arg = config.cameras_arg(cfg)
        self.assertIn("top: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}", arg)
        self.assertIn("index_or_path: /dev/video2", arg)

    def test_lerobot_home_follows_the_environment(self):
        old = os.environ.get("HF_LEROBOT_HOME")
        try:
            os.environ["HF_LEROBOT_HOME"] = str(Path(tempfile.gettempdir()) / "lr-home")
            self.assertEqual(config.lerobot_home(), Path(tempfile.gettempdir()) / "lr-home")
        finally:
            if old is None:
                os.environ.pop("HF_LEROBOT_HOME", None)
            else:
                os.environ["HF_LEROBOT_HOME"] = old


class LocalOverrides(unittest.TestCase):
    """hackathon.local.toml holds one computer's camera numbers and ports, and nothing shared."""

    def with_local(self, text: str) -> dict:
        tmp = Path(tempfile.mkdtemp()) / "hackathon.local.toml"
        tmp.write_text(text, encoding="utf-8")
        old = config.LOCAL_CONFIG_PATH
        config.LOCAL_CONFIG_PATH = tmp
        try:
            return config.load_config()
        finally:
            config.LOCAL_CONFIG_PATH = old
            shutil.rmtree(tmp.parent, ignore_errors=True)

    def test_camera_number_and_port_are_replaced(self):
        cfg = self.with_local('[cameras.wrist]\nindex_or_path = 7\n[robot]\nport = "COM9"\n')
        self.assertEqual(cfg["cameras"]["wrist"]["index_or_path"], 7)
        self.assertEqual(cfg["cameras"]["wrist"]["width"], 640)  # the rest of the camera is kept
        self.assertEqual(cfg["robot"]["port"], "COM9")
        self.assertEqual(sorted(cfg["cameras"]), ["top", "wrist"])

    def test_shared_values_cannot_be_overridden(self):
        for text in ('[robot]\nid = "other"\n', '[task]\ndescription = "something else"\n',
                     "[cameras.side]\nindex_or_path = 3\n", "[cameras.top]\nwidth = 1280\n"):
            with self.assertRaises(SystemExit, msg=text):
                self.with_local(text)

    def test_example_file_is_valid(self):
        cfg = self.with_local((ROOT / "hackathon.local.toml.example").read_text(encoding="utf-8"))
        self.assertEqual(sorted(cfg["cameras"]), ["top", "wrist"])


class DatasetLookup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.old = os.environ.get("HF_LEROBOT_HOME")
        os.environ["HF_LEROBOT_HOME"] = str(self.tmp)
        for ns, name in (("local", "battery_20261120_180000"), ("tester", "battery_20261121_090000"),
                         ("tester", "other_20261121_100000")):
            meta = self.tmp / ns / name / "meta"
            meta.mkdir(parents=True)
            (meta / "info.json").write_text(json.dumps({"total_episodes": 1}), encoding="utf-8")
        self.cfg = {"hf": {"user": "tester"}, "task": {"slug": "battery"}}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self.old is None:
            os.environ.pop("HF_LEROBOT_HOME", None)
        else:
            os.environ["HF_LEROBOT_HOME"] = self.old

    def test_newest_recording_of_the_current_account(self):
        repo_id, path = config.resolve_dataset(self.cfg, {}, None)
        self.assertEqual(repo_id, "tester/battery_20261121_090000")
        self.assertTrue((path / "meta" / "info.json").is_file())

    def test_bare_name_recorded_while_logged_out_is_found(self):
        repo_id, _ = config.resolve_dataset(self.cfg, {}, "battery_20261120_180000")
        self.assertEqual(repo_id, "local/battery_20261120_180000")

    def test_full_repo_id_is_kept(self):
        repo_id, path = config.resolve_dataset(self.cfg, {}, "someone/their_data")
        self.assertEqual(repo_id, "someone/their_data")
        self.assertEqual(path, self.tmp / "someone" / "their_data")


class CloudConfig(unittest.TestCase):
    def test_windows_paths_are_rewritten(self):
        data = {"policy": {"pretrained_path": r"C:\cache\models--lerobot--smolvla_base\snapshots\abc"},
                "output_dir": r"outputs\train\run1"}
        changed = cloud.fix_remote_config(data, "lerobot/smolvla_base")
        self.assertEqual(data["policy"]["pretrained_path"], "lerobot/smolvla_base")
        self.assertEqual(data["output_dir"], "outputs/train/run1")
        self.assertEqual(set(changed), {"policy.pretrained_path", "output_dir"})

    def test_policy_trained_from_scratch_is_left_alone(self):
        data = {"policy": {"pretrained_path": None}, "output_dir": "outputs/train/run1"}
        self.assertEqual(cloud.fix_remote_config(data, None), {})

    def test_local_only_base_model_is_refused(self):
        data = {"policy": {"pretrained_path": r"C:\models\mine"}, "output_dir": "outputs/train/run1"}
        with self.assertRaises(SystemExit):
            cloud.fix_remote_config(data, None)


class RecordingList(unittest.TestCase):
    """Four objects on four places: 24 arrangements, ordered so each episode is one swap of neighbours."""

    def setUp(self):
        with open(ROOT / "docs" / "strategy" / "recording-list.csv", newline="", encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        self.places = [tuple(r[f"place_{i}"] for i in range(1, 5)) for r in self.rows]

    def test_two_hundred_episodes_and_balanced_tnt_places(self):
        self.assertEqual(len(self.rows), 200)
        per_place = [sum(1 for r in self.rows if r["tnt_place"] == str(p)) for p in range(1, 5)]
        self.assertEqual(per_place, [50, 50, 50, 50])

    def test_every_arrangement_is_recorded(self):
        full = [p for p in self.places if "empty" not in p]
        self.assertEqual(len(set(full)), 24)
        for arrangement in full:
            self.assertEqual(sorted(arrangement), ["car", "duck", "green cube", "tnt"])
        for alone in (p for p in self.places if "empty" in p):
            self.assertEqual(sorted(alone), ["empty", "empty", "empty", "tnt"])

    def test_one_swap_of_neighbours_between_episodes(self):
        for before, after in zip(self.places, self.places[1:]):
            if "empty" in before or "empty" in after:
                continue
            changed = [i for i in range(4) if before[i] != after[i]]
            self.assertEqual(len(changed), 2, (before, after))
            self.assertEqual(changed[1] - changed[0], 1, (before, after))


class TwoConfigurationsAgree(unittest.TestCase):
    """scripts/*.sh read robot.env, `so` reads hackathon.toml. What a dataset, a calibration file
    or a trained policy depends on must be the same in both, or work done with one breaks the other."""

    @staticmethod
    def env_values() -> dict:
        out = {}
        for line in (ROOT / "robot.env.example").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip().strip('"')
        return out

    def test_shared_values_match(self):
        env, cfg = self.env_values(), config.load_config()
        self.assertEqual(env["FOLLOWER_ID"], cfg["robot"]["id"])
        self.assertEqual(env["LEADER_ID"], cfg["teleop"]["id"])
        self.assertEqual(env["TASK"], cfg["task"]["description"])
        self.assertEqual(sorted(cfg["cameras"]), ["top", "wrist"])  # the names scripts/_common.sh uses
        for cam in cfg["cameras"].values():
            self.assertEqual((int(env["CAM_W"]), int(env["CAM_H"]), int(env["CAM_FPS"])),
                             (cam["width"], cam["height"], cam["fps"]))


class ShellScripts(unittest.TestCase):
    SCRIPTS = [ROOT / "setup.sh", ROOT / "so", *sorted((ROOT / "scripts").glob("*.sh"))]

    def test_scripts_keep_unix_line_endings(self):
        self.assertGreaterEqual(len(self.SCRIPTS), 3)
        for script in self.SCRIPTS:
            self.assertNotIn(b"\r\n", script.read_bytes(), f"{script.name} has Windows line endings")

    # On Windows `bash` may be the WSL launcher, which fails when no distribution is installed.
    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "needs a real bash (Linux, macOS, WSL)")
    def test_scripts_parse(self):
        for script in self.SCRIPTS:
            res = subprocess.run(["bash", "-n", script.name], cwd=script.parent, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"{script.name}: {res.stderr}")


@unittest.skipUnless(shutil.which("lerobot-train"), "LeRobot is not installed in this environment")
def _ramp(start: float, end: float, t0: float, seconds: float, hz: int = 30) -> list[tuple[float, float]]:
    n = max(int(seconds * hz), 1)
    return [(t0 + i / hz, start + (end - start) * i / n) for i in range(n + 1)]


class DemoRetries(unittest.TestCase):
    """The decisions `so demo` takes between runs: grab or miss, run over, retry or not."""

    def test_holding_the_battery_is_seen(self):
        # rest -> open to 60 -> close until the battery stops the jaws at 30 -> hold -> open over the box
        samples = (_ramp(1.6, 60, 0, 1) + _ramp(60, 60, 1, 1) + _ramp(60, 30, 2, 0.4)
                   + _ramp(30, 30.5, 2.4, 1.5) + _ramp(30, 55, 3.9, 0.5))
        self.assertEqual(demo.grip_verdict(samples), "held")

    def test_closing_on_nothing_is_a_miss(self):
        samples = _ramp(1.6, 60, 0, 1) + _ramp(60, 1.2, 1, 0.5) + _ramp(1.2, 1.2, 1.5, 2)
        self.assertEqual(demo.grip_verdict(samples), "missed")

    def test_hovering_with_an_open_gripper_is_not_a_grab(self):
        samples = _ramp(1.6, 45, 0, 1) + _ramp(45, 45, 1, 3)
        self.assertNotEqual(demo.grip_verdict(samples), "held")

    def test_second_grab_after_a_miss_counts(self):
        samples = (_ramp(1.6, 60, 0, 1) + _ramp(60, 1.0, 1, 0.5) + _ramp(1.0, 60, 1.5, 0.7)
                   + _ramp(60, 25, 2.2, 0.4) + _ramp(25, 25, 2.6, 1))
        self.assertEqual(demo.grip_verdict(samples), "held")

    def test_gripper_that_never_opens(self):
        self.assertEqual(demo.grip_verdict(_ramp(1.6, 2.0, 0, 3)), "never_opened")
        self.assertEqual(demo.grip_verdict([]), "unknown")

    HOME = {"shoulder_lift.pos": -100.0, "elbow_flex.pos": 94.0}

    def feed(self, watch, lift_series):
        for i, lift in enumerate(lift_series):
            if watch.feed(i / 30, {"shoulder_lift.pos": lift, "elbow_flex.pos": 94.0}):
                return i / 30
        return None

    def test_run_ends_when_the_arm_is_back_and_still(self):
        out_and_back = [-100] * 15 + [-100 + 2 * i for i in range(35)] + [-30] * 30 + [-30 - 2 * i for i in range(36)] + [-101] * 60
        ended = self.feed(demo.MotionWatch(self.HOME), out_and_back)
        self.assertIsNotNone(ended)
        self.assertGreater(ended, (15 + 35 + 30 + 36) / 30)  # only after the return

    def test_pause_while_reaching_does_not_end_the_run(self):
        reach_and_pause = [-100 + 2 * i for i in range(35)] + [-30] * 120
        self.assertIsNone(self.feed(demo.MotionWatch(self.HOME), reach_and_pause))

    def test_arm_that_never_moves_does_not_end_the_run(self):
        self.assertIsNone(self.feed(demo.MotionWatch(self.HOME), [-100] * 150))

    def test_decisions(self):
        C = demo.Check
        self.assertEqual(demo.decide(C("held", "in_box"))[:2], (True, False))
        self.assertEqual(demo.decide(C("missed", "on_mat"))[:2], (False, True))
        self.assertEqual(demo.decide(C("held", "elsewhere"))[:2], (False, False))  # needs a human
        self.assertEqual(demo.decide(C("held", None))[:2], (True, False))  # no camera check: grip decides
        self.assertEqual(demo.decide(C("missed", None))[:2], (False, True))

    def test_sensecraft_camera_names_are_matched_by_role(self):
        rename = demo.camera_rename(["front", "gripper"], ["top", "wrist"])
        self.assertEqual(rename, {"observation.images.top": "observation.images.front",
                                  "observation.images.wrist": "observation.images.gripper"})
        self.assertEqual(demo.camera_rename(["top", "wrist"], ["top", "wrist"]), {})
        self.assertTrue(demo.trained_on_sensecraft_data(["gripper", "front"]))  # -> SenseCraft's calibration
        self.assertFalse(demo.trained_on_sensecraft_data(["top", "wrist"]))
        self.assertEqual(demo.camera_rename(["cam_a"], ["top"], demo.parse_rename("top=cam_a")),
                         {"observation.images.top": "observation.images.cam_a"})
        with self.assertRaises(SystemExit):
            demo.camera_rename(["cam_a", "cam_b"], ["top", "wrist"])  # no role in the names: must be explicit

    def test_manual_mode_logs_what_you_type(self):
        import queue
        import threading
        from types import SimpleNamespace
        from unittest import mock

        from sokit import evallog

        session = object.__new__(demo.Demo)  # no robot: only the keyboard loop is exercised
        session.opts = SimpleNamespace(label="sensecraft:battery test")
        session.shutdown = threading.Event()
        session._lines = queue.Queue()
        for line in ("\n", "s\n", "\n", "f missed grip place 3\n", "\n", "oops\n", "x\n", "q\n"):
            session._lines.put(line)
        session._run_policy = lambda: (12.3, "arm back at rest", "missed")
        log = Path(tempfile.mkdtemp()) / "eval.csv"
        with mock.patch.object(evallog, "EVAL_CSV", log), mock.patch("builtins.print"):
            session.manual_loop(read_stdin=False)
        with open(log, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["result"] for r in rows], ["success", "fail"])  # x is not logged
        self.assertTrue(rows[1]["note"].startswith("missed grip place 3 [12 s, arm back at rest, gripper missed]"))

    def test_keys_are_read_from_dot_env_without_overriding(self):
        from unittest import mock

        env_file = Path(tempfile.mkdtemp()) / ".env"
        env_file.write_text('gpt_api_key="sk-test-123"\nSOME_SETTING=from-file\n# comment\n', encoding="utf-8")
        with mock.patch.dict(os.environ, {"SOME_SETTING": "already-set"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("gpt_api_key", None)
            demo.load_env_file(env_file)
            self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-test-123")  # gpt_api_key is accepted
            self.assertEqual(os.environ["SOME_SETTING"], "already-set")    # never overridden

    def test_camera_check_provider(self):
        from unittest import mock

        with mock.patch.object(demo, "claude_available", return_value=False), \
             mock.patch.object(demo, "openai_available", return_value=True):
            self.assertEqual(demo.pick_provider("auto"), "openai")
            self.assertIsNone(demo.pick_provider("grip"))
            with self.assertRaises(SystemExit):
                demo.pick_provider("claude")
        with mock.patch.object(demo, "claude_available", return_value=False), \
             mock.patch.object(demo, "openai_available", return_value=False):
            self.assertIsNone(demo.pick_provider("auto"))  # no key at all: gripper only

    def test_sensecraft_storage_is_found(self):
        root = Path(tempfile.mkdtemp())
        calib = root / "calibration" / "lerobot" / "robots" / "so_follower"
        calib.mkdir(parents=True)
        (calib / "so100_follower.json").write_text("{}")
        for name, updated in (("old run", "2026-11-20T10:00"), ("battery final", "2026-11-21T10:00")):
            model_dir = root / "projects" / "p1" / "models" / name.replace(" ", "_")
            weights = model_dir / "bundle" / "pretrained_model"
            weights.mkdir(parents=True)
            (weights / "config.json").write_text('{"type": "act"}')
            (model_dir / "state.json").write_text(json.dumps(
                {"status": "ready", "display_name": name, "updated_at": updated, "steps": 30000,
                 "load_path": str(weights), "task_text": "battery sample"}))
        self.assertEqual(sensecraft.follower_calibration(root).robot_id, "so100_follower")
        self.assertEqual(sensecraft.pick_model(None, root).name, "battery final")
        self.assertEqual(sensecraft.pick_model("old", root).name, "old run")
        with self.assertRaises(SystemExit):
            sensecraft.pick_model("tnt", root)


@unittest.skipUnless(shutil.which("lerobot-train"), "LeRobot is not installed in this environment")
class DryRun(unittest.TestCase):
    """With LeRobot installed: `so` builds the same command on every operating system."""

    def run_so(self, *args):
        env = dict(os.environ, PYTHONUTF8="1", HF_LEROBOT_HOME=tempfile.mkdtemp(), HF_HUB_OFFLINE="1")
        res = subprocess.run([sys.executable, "-m", "sokit", "--dry-run", *args], cwd=ROOT, env=env,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def test_train_command(self):
        out = self.run_so("train", "--dataset", "tester/battery_demo", "--no-push")
        self.assertIn("lerobot-train", out)
        self.assertIn("--dataset.repo_id=tester/battery_demo", out)
        self.assertIn("--policy.type=act", out)
        self.assertNotIn("--policy.device", out)  # LeRobot picks cuda, mps or cpu by itself

    def test_explicit_device_is_forwarded(self):
        out = self.run_so("train", "--dataset", "tester/battery_demo", "--no-push", "--device", "mps")
        self.assertIn("--policy.device=mps", out)


if __name__ == "__main__":
    unittest.main()
