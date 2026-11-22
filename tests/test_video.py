"""Robot-free tests for recording the whole test on video (`so demo --record-video`, the panel's switch)."""

import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sokit import demo, panel  # noqa: E402

HAS_VIDEO = all(importlib.util.find_spec(m) for m in ("av", "cv2", "numpy"))


class FakeCamera:
    """Like LeRobot's OpenCVCamera.read_latest: the newest frame, or an error before the first one."""

    def __init__(self, value: int, fail_first: int = 0):
        import numpy as np

        self.frame = np.full((480, 640, 3), value, dtype=np.uint8)
        self.calls, self.fail_first = 0, fail_first

    def read_latest(self, max_age_ms: int = 500):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise RuntimeError("no frame yet")
        return self.frame


@unittest.skipUnless(HAS_VIDEO, "PyAV / OpenCV / numpy not installed")
class Recording(unittest.TestCase):
    def test_a_session_becomes_one_playable_video(self):
        import av

        path = Path(tempfile.mkdtemp()) / "session" / "test.mp4"
        cams = {"top": FakeCamera(90), "wrist": FakeCamera(160, fail_first=3)}
        video = demo.TestVideo(cams, ["top", "wrist"], path)
        video.start()
        video.status = "Attempt 1  run 1/3: arm running"
        time.sleep(1.2)
        video.status = "Attempt 1: SUCCESS in 1 run(s)"
        time.sleep(0.4)
        saved = video.stop()
        self.assertEqual(saved, path, video.error)
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            self.assertEqual((stream.codec_context.width, stream.codec_context.height), (1280, 480 + demo.TestVideo.BANNER))
            frames = sum(1 for _ in container.decode(stream))
        self.assertGreaterEqual(frames, 15)  # about 1.6 s at 15 frames per second

    def test_a_camera_that_never_delivers_still_gives_a_video(self):
        path = Path(tempfile.mkdtemp()) / "test.mp4"
        video = demo.TestVideo({"top": FakeCamera(90, fail_first=10**6)}, ["top", None], path)
        video.start()
        time.sleep(0.5)
        self.assertEqual(video.stop(), path, video.error)


class Wiring(unittest.TestCase):
    def test_demo_and_try_accept_the_option(self):
        self.assertTrue(demo.build_arg_parser().parse_args(["--record-video"]).record_video)
        self.assertFalse(demo.build_arg_parser().parse_args([]).record_video)

    def test_panel_switch_adds_the_option_to_robot_sessions_only(self):
        for cmd in ("demo", "try"):
            on = panel.build_command({"cmd": cmd, "source": "sensecraft", "record_video": True})
            off = panel.build_command({"cmd": cmd, "source": "sensecraft"})
            self.assertIn("--record-video", on.argv)
            self.assertNotIn("--record-video", off.argv)
        self.assertNotIn("--record-video", panel.build_command({"cmd": "teleop", "record_video": True}).argv)
        self.assertNotIn("--record-video", panel.build_command({"cmd": "demo", "record_video": "yes"}).argv)


if __name__ == "__main__":
    unittest.main()
