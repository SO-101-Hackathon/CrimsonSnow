"""Checks of the control panel (sokit/panel.py) that need no robot, no camera and no browser:
the commands it builds, how it reads `so demo` / `so try` output, its journal summaries, which
files it serves, who may talk to it, the camera preview rules (with a fake OpenCV), and whole
simulated sessions over HTTP (the panel's --mock mode).

    python -m unittest tests.test_panel -v
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sokit import panel  # noqa: E402
from sokit.panel import PanelError  # noqa: E402


class BuildCommand(unittest.TestCase):
    def test_demo_leaves_the_check_to_the_env_choice(self):
        c = panel.build_command({"cmd": "demo", "source": "sensecraft", "sensecraft": "battery final"}, python="py")
        self.assertEqual(c.argv, ["py", "-u", "-m", "sokit", "demo", "--sensecraft=battery final",
                                  "--tries=3", "--attempts=5", "--seconds=40"])
        self.assertEqual(c.shown, 'so demo "--sensecraft=battery final" --tries=3 --attempts=5 --seconds=40')
        self.assertTrue(c.hardware)
        self.assertTrue(c.prompts)

    def test_policy_check_and_dry_run(self):
        c = panel.build_command({"cmd": "demo", "source": "policy", "policy": "outputs/train/act/pretrained_model",
                                 "check": "local", "dry_run": True, "tries": "2", "attempts": 0, "seconds": 25},
                                python="py")
        self.assertEqual(c.argv, ["py", "-u", "-m", "sokit", "--dry-run", "demo",
                                  "--policy=outputs/train/act/pretrained_model", "--tries=2", "--attempts=0",
                                  "--check=local", "--seconds=25"])
        self.assertFalse(c.hardware)
        self.assertFalse(c.prompts)

    def test_try_teleop_cameras_doctor(self):
        self.assertEqual(panel.build_command({"cmd": "try", "source": "last", "seconds": 30}, python="py").argv,
                         ["py", "-u", "-m", "sokit", "try", "--seconds=30"])
        self.assertEqual(panel.build_command({"cmd": "teleop", "no_cameras": True}, python="py").argv[-2:],
                         ["teleop", "--no-cameras"])
        self.assertEqual(panel.build_command({"cmd": "cameras"}, python="py").argv[-1], "cameras")
        self.assertEqual(panel.build_command({"cmd": "doctor"}, python="py").argv[-1], "doctor")

    def test_bad_values_are_refused(self):
        bad = [
            {"cmd": "record"},
            {"cmd": "demo", "tries": 0},
            {"cmd": "demo", "tries": 2.5},
            {"cmd": "demo", "attempts": 100},
            {"cmd": "demo", "seconds": 1},
            {"cmd": "demo", "seconds": "nan"},
            {"cmd": "demo", "check": "rm -rf"},
            {"cmd": "demo", "source": "elsewhere"},
            {"cmd": "demo", "sensecraft": "--policy=evil"},   # would become an option of its own
            {"cmd": "demo", "source": "policy", "policy": ""},
            {"cmd": "demo", "source": "policy", "policy": "a\nb"},
            {"cmd": "demo", "sensecraft": "x" * 201},
            {"cmd": "demo", "tries": True},
            {"cmd": "doctor", "dry_run": True},               # doctor opens the hardware: no dry run
        ]
        for req in bad:
            with self.subTest(req=req), self.assertRaises(PanelError) as ctx:
                panel.build_command(req, python="py")
            self.assertEqual(ctx.exception.status, 400)

    def test_mock_mode_runs_the_simulated_program(self):
        c = panel.build_command({"cmd": "demo", "attempts": 2}, mock=True, mock_speed=0.5, mock_photos=False, python="py")
        self.assertEqual(c.argv[:6], ["py", "-u", "-m", "sokit.panel", "--mock-child", "demo"])
        self.assertIn("--attempts=2", c.argv)
        self.assertIn("--no-photos", c.argv)
        self.assertFalse(c.hardware)
        self.assertTrue(c.prompts)
        dry = panel.build_command({"cmd": "demo", "dry_run": True}, mock=True, python="py")
        self.assertEqual(dry.argv[3:6], ["sokit", "--dry-run", "demo"])  # a dry run is harmless: the real one


def _demo_session(p: panel.SessionParser) -> None:
    """Three attempts in the exact format sokit/demo.py prints: a success, a rescue by a retry, a failure."""
    feed = p.feed
    for line in ["[so] Start with the arm folded at rest: every run returns to the pose it starts from.", "",
                 "[demo] Policy: sensecraft:battery final dataset - ACT",
                 "[demo] Up to 3 runs per attempt. Check: local model looks at camera 'top' + gripper position",
                 "[demo] Ctrl+C stops the arm and ends the session.", "",
                 "[demo] Attempt 1: put the battery on its place, then press Enter (q + Enter = finish)"]:
        feed(line)
    p.on_input("")
    for line in ["[demo]   run 1: 19.6 s (arm back at rest) | grip: held | camera: in box",
                 "[demo]   -> SUCCESS: battery is in the box",
                 "[demo]      local model: The battery lies inside the cardboard box.",
                 "[demo] Attempt 1: SUCCESS in 25 s (1 run)", "",
                 "[demo] Attempt 2: put the battery on its place, then press Enter (q + Enter = finish)"]:
        feed(line)
    p.on_input("")
    for line in ["[demo]   run 1: 21.2 s (arm back at rest) | grip: missed | camera: on mat",
                 "[demo]   -> not done: battery is still on the mat",
                 "[demo]   running the policy again from the start pose...",
                 "[demo]   run 2: 18.4 s (arm back at rest) | grip: held | camera: in box",
                 "[demo]   -> SUCCESS: battery is in the box",
                 "[demo] Attempt 2: SUCCESS in 48 s (2 runs)", "",
                 "[demo] Attempt 3: put the battery on its place, then press Enter (q + Enter = finish)"]:
        feed(line)
    p.on_input("")
    for line in ["[demo]   run 1: 9.8 s (arm back at rest) | grip: never_opened | camera: elsewhere",
                 "[demo]   -> not done: battery left the mat: put it back by hand",
                 "[demo] Attempt 3: FAILED in 14 s (1 run)", "",
                 "[demo] 2/3 attempts succeeded, 1 of them thanks to a retry. Logged in journal/demo.csv; frames in x"]:
        feed(line)


class ReadOutput(unittest.TestCase):
    def test_demo_session(self):
        p = panel.SessionParser("demo", attempts_total=3, tries=3)
        self.assertEqual(p.phase, "starting")
        _demo_session(p)
        s = p.snapshot()
        self.assertEqual(s["policy"], "sensecraft:battery final dataset - ACT")
        self.assertEqual(s["tries"], 3)
        self.assertEqual([a["success"] for a in s["attempts"]], [True, True, False])
        self.assertEqual([a["rescued"] for a in s["attempts"]], [False, True, False])
        self.assertEqual([len(a["runs"]) for a in s["attempts"]], [1, 2, 1])
        self.assertEqual(s["attempts"][0]["runs"][0]["explanation"], "The battery lies inside the cardboard box.")
        self.assertEqual(s["attempts"][0]["runs"][0]["model"], "local model")
        self.assertEqual(s["last"]["camera"], "elsewhere")
        self.assertEqual(s["summary"], {"ok": 2, "total": 3, "rescued": 1})
        self.assertEqual((s["streak"], s["best_streak"]), (0, 2))
        self.assertEqual(s["phase"], "done")
        self.assertIsNone(s["prompt"])
        self.assertEqual(s["runs_seen"], 4)

    def test_prompts_and_stop(self):
        p = panel.SessionParser("demo", attempts_total=5, tries=3)
        p.feed("[demo] Attempt 1: put the battery on its place, then press Enter (q + Enter = finish)")
        self.assertEqual((p.prompt, p.attempt), ("attempt", 1))
        p.on_input("")
        self.assertEqual((p.prompt, p.phase, p.run), ("running", "running", 1))
        p.on_input("")  # Enter during a run stops the arm
        self.assertTrue(p.stop_requested)
        p.feed("[demo]   run 1: 3.2 s (stopped by you) | grip: unknown | camera: on mat")
        self.assertFalse(p.stop_requested)
        self.assertIsNone(p.prompt)
        p.feed("[demo] Attempt 2: put the battery on its place, then press Enter (q + Enter = finish)")
        p.on_input("q")
        self.assertEqual((p.prompt, p.phase), (None, "stopping"))
        p.on_exit(0)
        self.assertEqual((p.phase, p.exit_code), ("exited", 0))

    def test_try_session(self):
        p = panel.SessionParser("try")
        lines_a = ["[try] Policy: sensecraft:battery sample - ACT",
                   "[try] Attempt 1: set up the scene, then press Enter (q = finish)"]
        for line in lines_a:
            p.feed(line)
        p.on_input("")
        p.feed("[try]   22.0 s (arm back at rest), gripper: closed on something. The arm is back at its start pose.")
        p.feed("[try]   Result? s = success, f = fail (+ note), x = do not log")
        self.assertEqual(p.prompt, "result")
        p.on_input("f missed the grip")
        p.feed("[try] Attempt 2: set up the scene, then press Enter (q = finish)")
        p.on_input("")
        p.feed("[try]   20.0 s (arm back at rest), gripper: closed on something. The arm is back at its start pose.")
        p.feed("[try]   Result? s = success, f = fail (+ note), x = do not log")
        p.on_input("x")
        p.feed("[try] Attempt 2: set up the scene, then press Enter (q = finish)")  # x is not counted
        p.on_input("")
        p.feed("[try]   19.0 s (arm back at rest), gripper: closed on something. The arm is back at its start pose.")
        p.feed("[try]   Result? s = success, f = fail (+ note), x = do not log")
        p.on_input("S")
        p.feed("[try] 1/2 successes this session.")
        s = p.snapshot()
        self.assertEqual([a["result"] for a in s["attempts"]], ["f", "x", "s"])
        self.assertEqual([a["success"] for a in s["attempts"]], [False, None, True])
        self.assertEqual(s["attempts"][0]["note"], "missed the grip")
        self.assertEqual(s["summary"], {"ok": 1, "total": 2, "rescued": 0})
        self.assertEqual(s["streak"], 1)
        self.assertEqual(s["last"]["grip"], "closed on something")

    def test_the_lines_it_reads_are_still_printed_by_demo_py(self):
        """If someone rewords the prompts in sokit/demo.py, the panel must be updated too."""
        source = (ROOT / "sokit" / "demo.py").read_text(encoding="utf-8")
        for fragment in ["[demo] Policy: ", "runs per attempt. Check: ", "put the battery on its place, then press Enter",
                         "[demo]   run {run_no}: {run.seconds:.1f} s ({run.ended_by}) | grip: {run.check.grip} | {camera}",
                         "camera: {run.check.location.replace('_', ' ')}", "[demo]   -> ", "[demo]      ",
                         "[demo]   running the policy again from the start pose",
                         "in {result.seconds:.0f} s", "attempts succeeded, {rescued} of them thanks to a retry",
                         "[try] Policy: ", "set up the scene, then press Enter (q = finish)",
                         "The arm is back at its start pose.", "[try]   Result? s = success, f = fail (+ note), x = do not log",
                         "successes this session."]:
            self.assertIn(fragment, source)


class JournalAndPhotos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_demo_and_eval_summaries(self):
        demo_csv = self.root / "demo.csv"
        demo_csv.write_text(
            "date,time,policy,attempt,success,runs,rescued_by_retry,seconds,details\n"
            "2026-11-21,16:10:25,A,1,1,2,1,63.5,x\n"
            "2026-11-21,16:11:04,A,2,1,1,0,25.0,x\n"
            "2026-11-21,16:12:57,A,3,0,3,0,100.8,x\n"
            "2026-11-21,16:13:57,A,4,1,1,0,20.0,x\n"
            "2026-11-21,17:00:00,B,1,1,1,0,20.0,x\n", encoding="utf-8")
        groups = {g["policy"]: g for g in panel.summarize_demo_log(demo_csv)}
        self.assertEqual((groups["A"]["attempts"], groups["A"]["successes"], groups["A"]["rescued"]), (4, 3, 1))
        self.assertEqual((groups["A"]["runs"], groups["A"]["best_streak"]), (7, 2))
        self.assertEqual(panel.summarize_demo_log(demo_csv)[0]["policy"], "B")  # newest first
        eval_csv = self.root / "eval.csv"
        eval_csv.write_text("timestamp,policy,result,note\n2026-11-21 16:32:31,A,success,\n"
                            "2026-11-21 16:33:56,A,fail,up\n2026-11-21 16:34:00,A,success,\n", encoding="utf-8")
        (g,) = panel.summarize_eval_log(eval_csv)
        self.assertEqual((g["tries"], g["successes"], g["fails"]), (3, 2, 1))
        self.assertEqual(panel.summarize_demo_log(self.root / "missing.csv"), [])

    def _frames(self) -> Path:
        demo = self.root / "outputs" / "demo"
        for rel in ["20261121_160918/attempt01_run1_top.jpg", "20261121_160918/attempt01_run2_top.jpg",
                    "20261121_160918/attempt01_run2_wrist.jpg", "20261121_160918/attempt02_run1_top.jpg",
                    "20261121_162022/attempt01_run1_top.jpg", "20261121_162022/attempt01_run3_front.jpg",
                    "20261121_162022/attempt01_run3_gripper.jpg", "20261121_162022/notes.txt",
                    "not_a_session/attempt09_run9_top.jpg"]:
            f = demo / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"\xff\xd8 fake jpeg \xff\xd9")
        return demo

    def test_latest_check_photo(self):
        demo = self._frames()
        latest = panel.latest_check_photo([demo], root=self.root)
        self.assertEqual((latest["session"], latest["attempt"], latest["run"]), ("20261121_162022", 1, 3))
        self.assertEqual(latest["scene"], "outputs/demo/20261121_162022/attempt01_run3_front.jpg")
        self.assertEqual(latest["wrist"], "outputs/demo/20261121_162022/attempt01_run3_gripper.jpg")
        self.assertIsNone(panel.latest_check_photo([self.root / "nothing"], root=self.root))

    def test_only_images_inside_the_allowed_folders_are_served(self):
        demo = self._frames()
        (self.root / "secret.jpg").write_bytes(b"x")
        (self.root / ".env").write_text("gpt_api_key=do-not-serve", encoding="utf-8")
        ok = panel.resolve_photo("outputs/demo/20261121_162022/attempt01_run1_top.jpg", [demo], root=self.root)
        self.assertIsNotNone(ok)
        for rel in ["outputs/demo/../../secret.jpg", "outputs/demo/20261121_162022/../../../secret.jpg",
                    str((self.root / "secret.jpg").resolve()), "outputs/demo/20261121_162022/notes.txt",
                    ".env", "", "outputs/demo/missing.jpg", "outputs/demo/20261121_162022/attempt01_run1_top.jpg\x00"]:
            with self.subTest(rel=rel):
                self.assertIsNone(panel.resolve_photo(rel, [demo], root=self.root))

    def test_labelled_frames_follow_the_demo_log(self):
        demo = self._frames()
        csv_path = self.root / "demo.csv"
        csv_path.write_text(
            "date,time,policy,attempt,success,runs,rescued_by_retry,seconds,details\n"
            '2026-11-21,16:10:25,A,1,1,2,1,63.5,"run 1: 40 s (time limit), grip held, camera on_mat -> battery is '
            'still on the mat; run 2: 12 s (arm back at rest), grip missed, camera in_box -> battery is in the box"\n'
            '2026-11-21,16:11:04,A,2,1,1,0,25.0,"run 1: grip held, camera n/a -> gripper closed on the battery"\n',
            encoding="utf-8")
        frames = panel.labelled_frames(demo, csv_path)
        self.assertEqual(sorted(frames), ["in_box", "on_mat"])
        scene, wrist = frames["in_box"][0]
        self.assertEqual((scene.name, wrist.name), ("attempt01_run2_top.jpg", "attempt01_run2_wrist.jpg"))
        self.assertEqual(frames["on_mat"][0][0].name, "attempt01_run1_top.jpg")


class SettingsWithoutSecrets(unittest.TestCase):
    def test_env_setting_and_key_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("# choice\nexport RETRY_CHECK = \"local\"   # chatgpt | local | claude\n"
                           "gpt_api_key=sk-test-not-real\nANTHROPIC_API_KEY=\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=False):
                for name in ("RETRY_CHECK", "OPENAI_API_KEY", "gpt_api_key", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
                    os.environ.pop(name, None)
                self.assertEqual(panel.env_setting("RETRY_CHECK", env), "local")
                os.environ["RETRY_CHECK"] = "openai"  # the environment wins, as in sokit.demo.load_env_file
                self.assertEqual(panel.env_setting("RETRY_CHECK", env), "openai")
                self.assertEqual(panel.keys_present(env), {"openai": True, "claude": False})
                with self.assertRaises(ValueError):
                    panel.env_setting("gpt_api_key", env)
                self.assertNotIn("sk-test", json.dumps(panel.keys_present(env)))


class AccessRules(unittest.TestCase):
    def test_host_header(self):
        ok = ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "LOCALHOST:8765"]
        bad = [None, "", "127.0.0.1:9999", "evil.example:8765", "127.0.0.1.evil.example:8765", "[::1", "localhost"]
        for host in ok:
            self.assertTrue(panel.host_allowed(host, 8765, lan=False), host)
        for host in bad:
            self.assertFalse(panel.host_allowed(host, 8765, lan=False), host)
        self.assertFalse(panel.host_allowed("192.168.1.20:8765", 8765, lan=False))
        self.assertTrue(panel.host_allowed("192.168.1.20:8765", 8765, lan=True))
        self.assertTrue(panel.host_allowed("laptop:8765", 8765, lan=True, extra_names=("laptop",)))
        self.assertFalse(panel.host_allowed("rebind.evil.example:8765", 8765, lan=True, extra_names=("laptop",)))

    def test_origin_header(self):
        self.assertTrue(panel.origin_allowed(None, 8765, lan=False))
        self.assertTrue(panel.origin_allowed("http://127.0.0.1:8765", 8765, lan=False))
        for origin in ("http://evil.example", "null", "https://127.0.0.1:8765", "http://127.0.0.1:1234"):
            self.assertFalse(panel.origin_allowed(origin, 8765, lan=False), origin)


class _FakeCapture:
    opened: list = []

    def __init__(self, source, *api):
        self.source, self.api, self.released, self.props = source, api, False, {}
        _FakeCapture.opened.append(self)

    def isOpened(self):  # noqa: N802 - OpenCV's name
        return True

    def set(self, prop, value):
        self.props[prop] = value
        return True

    def read(self):
        time.sleep(0.01)
        return True, "frame"

    def release(self):
        self.released = True


def _fake_cv2():
    return types.SimpleNamespace(
        VideoCapture=_FakeCapture, CAP_DSHOW=700, CAP_PROP_FOURCC=6, CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_FPS=5, IMWRITE_JPEG_QUALITY=1, VideoWriter_fourcc=lambda *c: 1196444237,
        imencode=lambda ext, frame, params: (True, b"\xff\xd8jpeg\xff\xd9"))


class SenseCraftGuard(unittest.TestCase):
    def test_robot_commands_wait_until_sensecraft_is_closed(self):
        p = panel.Panel(sensecraft_probe=lambda: True)
        for req in ({"cmd": "demo"}, {"cmd": "try"}, {"cmd": "teleop"}, {"cmd": "cameras"}, {"cmd": "doctor"}):
            with self.subTest(req=req), self.assertRaises(PanelError) as ctx:
                p.start_command(req)
            self.assertEqual(ctx.exception.status, 409)
            self.assertIn("SenseCraft", ctx.exception.message)
        self.assertIsNone(p.child)  # nothing was started


class CameraPreview(unittest.TestCase):
    CAMS = {"top": {"index_or_path": 1, "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}}

    def test_refused_while_sensecraft_runs_in_mock_mode_or_during_a_command(self):
        busy = panel.Panel(sensecraft_probe=lambda: True, cv2_loader=_fake_cv2)
        with self.assertRaises(PanelError) as ctx:
            busy.cameras.set_enabled(True)
        self.assertIn("SenseCraft", ctx.exception.message)
        with self.assertRaises(PanelError):
            panel.Panel(mock=True, sensecraft_probe=lambda: False, cv2_loader=_fake_cv2).cameras.set_enabled(True)
        free = panel.Panel(sensecraft_probe=lambda: False, cv2_loader=_fake_cv2)
        with mock.patch.object(free, "running", return_value=True):
            self.assertIn("command is running", free.cameras.blocked())

    def test_stream_opens_reads_and_releases(self):
        _FakeCapture.opened = []
        p = panel.Panel(sensecraft_probe=lambda: False, cv2_loader=_fake_cv2)
        with mock.patch.object(p, "camera_configs", return_value=self.CAMS):
            with self.assertRaises(PanelError):
                p.cameras.check_stream("top")  # not switched on yet
            p.cameras.set_enabled(True)
            with self.assertRaises(PanelError):
                p.cameras.check_stream("nope")
            cam = p.cameras.check_stream("top")
            got: list[bytes] = []

            class Enough(Exception):
                pass

            def write(jpeg: bytes) -> None:
                got.append(jpeg)
                if len(got) == 3:
                    raise Enough

            with self.assertRaises(Enough):
                p.cameras.stream("top", cam, write)
            self.assertEqual(got[0], b"\xff\xd8jpeg\xff\xd9")
            p.cameras.release_all()
        (cap,) = _FakeCapture.opened
        self.assertEqual(cap.source, 1)
        self.assertTrue(cap.released)
        self.assertFalse(p.cameras.enabled)
        if panel.R.IS_WINDOWS:
            self.assertEqual(cap.api, (700,))  # DirectShow: MSMF fails to open these cameras


class SimulatedSessions(unittest.TestCase):
    """The real server and the --mock programs, driven through the HTTP API like the page does."""

    @classmethod
    def setUpClass(cls):
        cls.panel = panel.Panel(mock=True, mock_speed=0.02, mock_photos=False, port=0, sensecraft_probe=lambda: True)
        cls.server = panel.PanelServer(cls.panel)
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        cls.thread.start()
        cls.port = cls.panel.port

    @classmethod
    def tearDownClass(cls):
        cls.panel.close(wait=5)
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, path, body=None, token=True, headers=None, server_port=None):
        conn = http.client.HTTPConnection("127.0.0.1", server_port or self.port, timeout=15)
        h = dict(headers or {})
        if token:
            h.setdefault("X-Panel-Token", self.panel.token)
        data = None
        if body is not None:
            data = json.dumps(body)
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        try:
            return res.status, json.loads(raw), res
        except ValueError:
            return res.status, raw.decode("utf-8", "replace"), res

    def state(self):
        status, s, _ = self.call("GET", "/api/state?since=0")
        self.assertEqual(status, 200)
        return s

    def wait_for(self, predicate, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            s = self.state()
            if predicate(s):
                return s
            time.sleep(0.03)
        self.fail(f"timed out; last state: {json.dumps(s)[:1500]}")

    def wait_idle(self):
        return self.wait_for(lambda s: not (s["proc"] and s["proc"]["running"]))

    def answer(self, prompt, text, expect=None):
        self.wait_for(lambda s: s["proc"]["running"] and s["session"]["prompt"] == prompt)
        status, body, _ = self.call("POST", "/api/input", {"text": text, "expect": expect or prompt})
        self.assertEqual(status, 200, body)

    def test_a_page_and_access_checks(self):
        status, html, res = self.call("GET", "/", token=False)
        self.assertEqual(status, 200)
        self.assertIn(self.panel.token, html)
        self.assertIn(f"nonce-{self.panel.nonce}", res.getheader("Content-Security-Policy"))
        self.assertNotIn("__PANEL_", html)
        self.assertEqual(self.call("GET", "/api/state", token=False)[0], 403)
        self.assertEqual(self.call("GET", "/api/state", headers={"X-Panel-Token": "wrong"})[0], 403)
        self.assertEqual(self.call("POST", "/api/run", {"cmd": "demo"}, token=False)[0], 403)
        self.assertEqual(self.call("GET", "/api/state", headers={"Host": f"evil.example:{self.port}"})[0], 403)
        self.assertEqual(self.call("POST", "/api/abort", {}, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.call("GET", f"/api/state?t={self.panel.token}", token=False)[0], 200)
        for rel in ("../.env", ".env", "sokit/panel.py", "outputs/demo/../../.env"):
            self.assertEqual(self.call("GET", f"/api/photo?path={rel}")[0], 404, rel)
        self.assertEqual(self.call("POST", "/api/input", {"text": "", "expect": "attempt"})[0], 409)  # nothing runs
        status, models, _ = self.call("GET", "/api/models")
        self.assertEqual(status, 200)
        self.assertIsInstance(models["models"], list)
        self.assertEqual(self.call("GET", "/api/results")[0], 200)
        s = self.state()
        self.assertTrue(s["status"]["mock"])
        self.assertTrue(s["status"]["sensecraft"])  # the banner shows, mock commands still run

    def test_b_demo_with_a_rescue(self):
        self.wait_idle()
        status, body, _ = self.call("POST", "/api/run", {"cmd": "demo", "attempts": 3, "tries": 3, "check": "local"})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["mocked"])
        self.assertEqual(self.call("POST", "/api/run", {"cmd": "demo"})[0], 409)  # one at a time
        self.answer("attempt", "")
        self.assertEqual(self.call("POST", "/api/input", {"text": "", "expect": "attempt"})[0], 409)  # double click
        self.answer("attempt", "")
        self.answer("attempt", "")
        s = self.wait_for(lambda s: s["session"]["summary"] is not None)
        x = s["session"]
        self.assertEqual(x["summary"], {"ok": 3, "total": 3, "rescued": 1})
        self.assertEqual([a["success"] for a in x["attempts"]], [True, True, True])
        self.assertEqual([a["rescued"] for a in x["attempts"]], [False, True, False])
        self.assertEqual(x["attempts"][1]["runs"][0]["camera"], "on mat")
        self.assertEqual(x["streak"], 3)
        self.assertIn("local model", x["check"])
        s = self.wait_idle()
        self.assertEqual(s["proc"]["exit_code"], 0)
        self.assertTrue(any("simulated" in t for _, t in s["lines"]))

    def test_c_try_finish_from_the_page(self):
        self.wait_idle()
        self.assertEqual(self.call("POST", "/api/run", {"cmd": "try", "source": "last"})[0], 200)
        self.answer("attempt", "")
        self.answer("result", "f slipped out")
        self.answer("attempt", "")
        self.answer("result", "s")
        self.wait_for(lambda s: s["session"]["prompt"] == "attempt")
        self.assertEqual(self.call("POST", "/api/finish", {})[0], 200)
        s = self.wait_idle()
        x = s["session"]
        self.assertEqual([a["result"] for a in x["attempts"]], ["f", "s"])
        self.assertEqual(x["attempts"][0]["note"], "slipped out")
        self.assertEqual(x["summary"], {"ok": 1, "total": 2, "rescued": 0})

    def test_d_abort_ends_a_program_without_prompts(self):
        self.wait_idle()
        self.assertEqual(self.call("POST", "/api/run", {"cmd": "teleop"})[0], 200)
        self.wait_for(lambda s: any("teleop running" in t for _, t in s["lines"]))
        self.assertEqual(self.call("POST", "/api/abort", {})[0], 200)
        s = self.wait_idle()
        self.assertFalse(s["proc"]["running"])
        self.assertEqual(self.call("POST", "/api/abort", {})[0], 409)

    def test_e_stop_arm_during_a_run(self):
        self.wait_idle()
        slow = panel.Panel(mock=True, mock_speed=1.0, mock_photos=False, port=0, sensecraft_probe=lambda: False)
        server = panel.PanelServer(slow)
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        try:
            def call(method, path, body=None):
                return self.call(method, path, body, headers={"X-Panel-Token": slow.token}, server_port=slow.port)

            def get():
                return call("GET", "/api/state?since=0")[1]

            def wait(pred, timeout=20.0):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    s = get()
                    if pred(s):
                        return s
                    time.sleep(0.03)
                self.fail("timed out")

            self.assertEqual(call("POST", "/api/run", {"cmd": "demo", "attempts": 1, "tries": 1})[0], 200)
            wait(lambda s: s["session"]["prompt"] == "attempt")
            self.assertEqual(call("POST", "/api/input", {"text": "", "expect": "attempt"})[0], 200)
            time.sleep(0.5)
            self.assertEqual(call("POST", "/api/input", {"text": "", "expect": "running"})[0], 200)
            s = wait(lambda s: s["session"]["last"] is not None)
            self.assertEqual(s["session"]["last"]["ended_by"], "stopped by you")
            wait(lambda s: not s["proc"]["running"])
        finally:
            slow.close(wait=5)
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
