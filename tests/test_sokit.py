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

from sokit import cloud, config, ports, runner  # noqa: E402


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
    def test_every_arrangement_is_listed_once(self):
        with open(ROOT / "docs" / "strategy" / "recording-list.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 130)
        main = [tuple(r[f"place_{i}"] for i in range(1, 6)) for r in rows[:120]]
        self.assertEqual(len(set(main)), 120)
        for arrangement in main:
            self.assertEqual(sorted(arrangement), ["battery", "cap", "cardboard", "cork", "empty"])


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
