"""Robot-free tests for the local camera check (sokit/vision.py) and how `so demo` picks its check."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sokit import demo, vision  # noqa: E402

HAS_TORCH = all(importlib.util.find_spec(m) for m in ("torch", "torchvision"))
HAS_PARQUET = all(importlib.util.find_spec(m) for m in ("pandas", "pyarrow"))


def trace(*parts):
    """Gripper positions from (value, frames) pieces; ramps are a few frames long."""
    out = []
    for value, frames in parts:
        out += [float(value)] * frames
    return out


# rest, open wide, close on the battery (stops at 36), carry, open over the box, close, rest
PICK_AND_PLACE = trace((1.6, 30), (60, 30), (50, 2), (36, 60), (60, 20), (1.6, 40))


class Labels(unittest.TestCase):
    def test_one_grab_is_found(self):
        found = vision.grabs(PICK_AND_PLACE, fps=30)
        self.assertEqual(len(found), 1)
        g = found[0]
        self.assertEqual(g.closing, 59)    # last frame at its widest, just before it closes
        self.assertEqual(g.held, 62)       # the steady hold at 36 starts after the 2-frame ramp
        self.assertEqual(g.released, 122)  # first frame open again

    def test_miss_then_second_grab(self):
        grip = trace((1.6, 20), (60, 20), (1.0, 20), (60, 20), (30, 40), (70, 10), (1.6, 10))
        found = vision.grabs(grip, fps=30)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0].closing, found[0].held), (79, 81))  # the second grab

    def test_no_grab_no_labels(self):
        self.assertEqual(vision.grabs(trace((1.6, 300))), [])
        self.assertIsNone(vision.episode_labels(trace((1.6, 300))))
        # held and never let go (recording cut short): no "in the box" frames, so no labels
        self.assertIsNone(vision.episode_labels(trace((1.6, 30), (60, 30), (36, 200))))

    def test_label_ranges_keep_away_from_the_transitions(self):
        lab = vision.episode_labels(PICK_AND_PLACE, fps=30)
        self.assertEqual(lab.ranges["on_mat"], (0, 59 - 6))         # 0.2 s before closing
        self.assertEqual(lab.ranges["in_gripper"], (62 + 9, 122 - 9))
        self.assertEqual(lab.ranges["in_box"], (122 + 30, len(PICK_AND_PLACE) - 1))
        self.assertEqual(lab.released, 122)

    def test_spread(self):
        self.assertEqual(vision.spread(0, 100, 3), [0, 50, 100])
        self.assertEqual(vision.spread(5, 7, 6), [5, 6, 7])
        self.assertEqual(vision.spread(0, 9, 1), [9])
        self.assertEqual(vision.spread(9, 0, 3), [])

    def test_every_fifth_episode_is_held_out(self):
        self.assertEqual([e for e in range(15) if vision.split_of(e) == "val"], [4, 9, 14])

    def test_decision_thresholds(self):
        self.assertEqual(vision.decide_location({"in_box": 0.85, "on_mat": 0.1, "in_gripper": 0.05})[0], "in_box")
        self.assertIsNone(vision.decide_location({"in_box": 0.7, "on_mat": 0.2, "in_gripper": 0.1})[0])
        self.assertEqual(vision.decide_location({"in_box": 0.2, "on_mat": 0.65, "in_gripper": 0.15})[0], "on_mat")
        self.assertIsNone(vision.decide_location({"in_box": 0.3, "on_mat": 0.5, "in_gripper": 0.2})[0])
        location, text = vision.decide_location({"in_box": 0.05, "on_mat": 0.05, "in_gripper": 0.9})
        self.assertEqual(location, "in_gripper")
        self.assertTrue(text.startswith("in the gripper 90%"))


class SenseCraftDatasets(unittest.TestCase):
    def test_found_and_default_is_the_biggest(self):
        root = Path(tempfile.mkdtemp())
        for ds, name, eps, when in (("ds_a", "battery sample", 108, "2026-11-21T11:00"),
                                    ("ds_b", "battery final dataset", 257, "2026-11-21T18:00"),
                                    ("ds_c", "empty", 0, "2026-11-21T19:00")):
            folder = root / "projects" / "proj_1" / "datasets" / ds
            (folder / "meta").mkdir(parents=True)
            (folder / "state.json").write_text(json.dumps({"status": "ready", "dataset_name": name, "updated_at": when}))
            (folder / "meta" / "info.json").write_text(json.dumps({"total_episodes": eps}))
        found = vision.sensecraft_datasets(root)
        self.assertEqual([d["id"] for d in found], ["ds_b", "ds_a"])  # newest first, empty one left out
        self.assertEqual(vision.pick_sensecraft_dataset(None, root)["id"], "ds_b")
        self.assertEqual(vision.pick_sensecraft_dataset("battery sample", root)["id"], "ds_a")
        with self.assertRaises(SystemExit):
            vision.pick_sensecraft_dataset("duck", root)

    def test_overhead_camera_is_found_by_name(self):
        info = {"features": {"observation.images.front": {"dtype": "video"},
                             "observation.images.gripper": {"dtype": "video"}, "action": {"dtype": "float32"}}}
        self.assertEqual(vision.scene_camera_key(info), "observation.images.front")
        self.assertEqual(vision.scene_camera_key(info, "gripper"), "observation.images.gripper")
        with self.assertRaises(SystemExit):
            vision.scene_camera_key(info, "top")


@unittest.skipUnless(HAS_PARQUET, "pandas/pyarrow not installed")
class FramePlan(unittest.TestCase):
    def test_frames_are_planned_from_a_recorded_dataset(self):
        import pandas as pd

        root = Path(tempfile.mkdtemp())
        names = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos", "wrist_roll.pos", "gripper.pos"]
        info = {"fps": 30, "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
                "features": {"observation.state": {"names": names}, "observation.images.front": {"dtype": "video"}}}
        (root / "meta" / "episodes" / "chunk-000").mkdir(parents=True)
        (root / "data" / "chunk-000").mkdir(parents=True)
        (root / "meta" / "info.json").write_text(json.dumps(info))
        n = len(PICK_AND_PLACE)
        rows, eps = [], []
        for e in range(5):
            for k, g in enumerate(PICK_AND_PLACE):
                lift = 0.0 if k < 20 or k > n - 20 else 40.0  # folded at rest at both ends
                pan = -35.0 if 100 <= k <= 125 else 0.0       # over the box when letting go
                rows.append({"episode_index": e, "frame_index": k, "observation.state": [pan, lift, lift, 0, 0, g]})
            eps.append({"episode_index": e, "length": n, "videos/observation.images.front/chunk_index": 0,
                        "videos/observation.images.front/file_index": 0,
                        "videos/observation.images.front/from_timestamp": e * n / 30})
        pd.DataFrame(rows).to_parquet(root / "data" / "chunk-000" / "file-000.parquet")
        pd.DataFrame(eps).to_parquet(root / "meta" / "episodes" / "chunk-000" / "file-000.parquet")

        planned, wanted, stats = vision.plan_frames(root, "t")
        self.assertEqual(stats["labelled"], 5)
        self.assertEqual(stats["camera"], "observation.images.front")
        per_episode = sum(vision.PICKS.values())
        self.assertEqual(len(planned), 5 * per_episode)
        self.assertEqual({r["split"] for r in planned if r["episode"] == 4}, {"val"})
        first = [r for r in planned if r["episode"] == 0 and r["frame"] == 0][0]
        self.assertEqual((first["label"], first["rest"]), ("on_mat", 1))
        video = root / "videos" / "observation.images.front" / "chunk-000" / "file-000.mp4"
        # episode 2's frame k sits at video frame 2 * n + k in the shared file
        k = [r for r in planned if r["episode"] == 2][0]["frame"]
        self.assertIn(2 * n + k, wanted[video])


class CheckChoice(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for name in ("RETRY_CHECK", "LOCAL_CHECK_MODEL", "OPENAI_CHECK_MODEL", "CLAUDE_CHECK_MODEL"):
            os.environ.pop(name, None)

    def tearDown(self):
        self.env.stop()

    def _pick(self, setting, claude=False, openai=False, local=False):
        if setting is not None:
            os.environ["RETRY_CHECK"] = setting
        with mock.patch.object(demo, "claude_available", return_value=claude), \
             mock.patch.object(demo, "openai_available", return_value=openai), \
             mock.patch.object(demo, "local_available", return_value=local):
            return demo.pick_provider("auto")

    def test_dot_env_picks_the_check(self):
        self.assertEqual(self._pick("local", local=True), "local")
        self.assertEqual(self._pick("opencv", local=True), "local")
        self.assertEqual(self._pick("chatgpt", claude=True, openai=True), "openai")
        self.assertEqual(self._pick("Claude", claude=True, openai=True), "claude")
        self.assertIsNone(self._pick("grip", claude=True, openai=True, local=True))

    def test_without_the_setting_nothing_changes(self):
        self.assertEqual(self._pick(None, claude=True, openai=True, local=True), "claude")
        self.assertEqual(self._pick(None, openai=True, local=True), "openai")
        self.assertIsNone(self._pick(None, local=True))  # as before: no key -> gripper only

    def test_bad_or_unusable_setting_stops_with_a_message(self):
        with self.assertRaises(SystemExit):
            self._pick("gemini")
        with self.assertRaises(SystemExit):
            self._pick("local", local=False)  # not trained yet
        with self.assertRaises(SystemExit):
            self._pick("chatgpt", openai=False)  # no key

    def test_explicit_flag_beats_the_dot_env_setting(self):
        os.environ["RETRY_CHECK"] = "local"
        with mock.patch.object(demo, "claude_available", return_value=True):
            self.assertEqual(demo.pick_provider("claude"), "claude")

    def test_model_per_check(self):
        self.assertEqual(demo.default_model("openai"), "gpt-5.5")
        self.assertEqual(demo.default_model("local"), "outputs/vision/model/battery_check.pt")
        os.environ["OPENAI_CHECK_MODEL"] = "gpt-5.4-mini"
        self.assertEqual(demo.default_model("openai"), "gpt-5.4-mini")
        self.assertEqual(demo.default_model(None), "")

    def test_dot_env_example_documents_every_choice(self):
        text = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
        self.assertIn("RETRY_CHECK=", text)
        for word in ("local", "openai", "claude", "grip"):
            self.assertIn(word, text)


@unittest.skipUnless(HAS_TORCH, "torch/torchvision not installed")
class Inference(unittest.TestCase):
    def test_a_saved_model_answers_in_the_demo_format(self):
        import torch

        model = vision.build_model(pretrained=False)
        with torch.no_grad():
            model.fc.weight.zero_()
            model.fc.bias.copy_(torch.tensor([5.0, 0.0, 0.0]))  # always "in the box", ~99 %
        path = Path(tempfile.mkdtemp()) / "m.pt"
        torch.save({"state_dict": model.state_dict(), "meta": {"classes": list(vision.CLASSES)}}, path)
        with mock.patch.dict(os.environ, {"LOCAL_CHECK_DEVICE": "cpu"}):
            from PIL import Image
            import io

            buf = io.BytesIO()
            Image.new("RGB", (640, 480), (80, 80, 80)).save(buf, format="JPEG")
            answer = vision.verdict(buf.getvalue(), model_path=path)
            self.assertEqual(answer["battery_location"], "in_box")
            self.assertIn(answer["battery_location"], demo.LOCATIONS)
            self.assertTrue(answer["explanation"].startswith("in the box 99%"))
            with torch.no_grad():
                model.fc.bias.copy_(torch.tensor([0.0, 0.0, 0.0]))  # a third each: unsure
            unsure = path.with_name("u.pt")
            torch.save({"state_dict": model.state_dict(), "meta": {"classes": list(vision.CLASSES)}}, unsure)
            with self.assertRaises(demo.CheckFailed):
                vision.verdict(buf.getvalue(), model_path=unsure)

    def test_missing_model_is_a_check_failure_not_a_crash(self):
        with self.assertRaises(demo.CheckFailed):
            vision.LocalChecker.load(Path(tempfile.mkdtemp()) / "none.pt")


if __name__ == "__main__":
    unittest.main()


class UnsureCheckDoesNotStopTheDemo(unittest.TestCase):
    """`python -m sokit.demo` runs demo.py as __main__, so vision raises a *different* CheckFailed class."""

    def test_foreign_check_failed_becomes_ours(self):
        class CheckFailed(Exception):  # stands in for sokit.demo.CheckFailed seen from __main__
            pass

        with mock.patch.object(vision, "verdict", side_effect=CheckFailed("our model is unsure (on the mat 49%)")):
            with self.assertRaises(demo.CheckFailed) as ctx:
                demo.ask_local(b"jpeg", None, model="m.pt", timeout=1)
        self.assertIn("unsure", str(ctx.exception))

    def test_other_errors_are_not_disguised(self):
        with mock.patch.object(vision, "verdict", side_effect=RuntimeError("cuda out of memory")):
            with self.assertRaises(RuntimeError):
                demo.ask_local(b"jpeg", None, model="m.pt", timeout=1)
