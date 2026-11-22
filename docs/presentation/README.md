# Pitch deck (5 minutes)

[CrimsonSnow-pitch.pptx](CrimsonSnow-pitch.pptx): 9 slides, 4:40 of talk. The spoken script and the
time for each slide are in the speaker notes (PowerPoint: View > Notes, or Presenter View).

| # | Slide | For the jury | Time |
|---|---|---|---|
| 1 | CrimsonSnow | who we are, the task in one line | 0:15 |
| 2 | Find the battery, drop it in the box | the task and why it matters (utility) | 0:30 |
| 3 | Only the battery, even in a pile of junk | clutter test: 14 other objects, picked first try | 0:20 |
| 4 | 257 demonstrations, aimed at our failures | data, iteration on failures | 0:45 |
| 5 | ACT: 100,000 steps on an RTX 5090 | the policy and its training | 0:30 |
| 6 | If it fails, it tries again | closed loop with automatic retries | 0:45 |
| 7 | Our own vision model checks the box | innovation: labels for free from the gripper | 0:45 |
| 8 | Built to be repeated | `so` helper, CI, control panel, open repo | 0:25 |
| 9 | Live now: five attempts, hands off | 3/7 by hand → 24/24, hand-over to the live demo | 0:25 |

Rebuild after changing a number (all of them are in `NUMBERS` at the top of the script):

```bash
pip install python-pptx                      # any Python 3.10+, not needed in the lerobot env
python docs/presentation/build_deck.py       # uses the pictures in img/
python docs/presentation/build_deck.py --refresh-images           # copy them again from outputs/ (team laptop)
python docs/presentation/build_deck.py --panel-shot panel.png     # new control-panel screenshot for slide 8
```

The clutter-test pictures (`img/trash_*.jpg`) are stills of `outputs/demo/test video trash/test.mp4`
(22 Nov 2026) and are not refreshed.

# 1-minute video for the judges

`outputs/video/CrimsonSnow-1min.mp4` (git-ignored, 15 MB): 1920×1080, 30 fps, 60 s, no sound; the voice-over
is added on top. Sections follow the script: 0:00 the need (Blender intro + three sourced facts), 0:10 the task
(the clutter test, overhead + wrist camera), 0:23 the data, 0:42 retries and our vision model, 0:56 close (24/24).

```bash
# 1. the intro: open intro.blend in Blender 4.2+ and render the scene CrimsonSnow_Intro (frames 1-240, Eevee)
#    into outputs/video/intro/  (frame_0001.png ...)
# 2. the video, from the intro, the test recordings in outputs/demo and the dataset cache in outputs/vision
python docs/presentation/build_video.py
python docs/presentation/build_video.py --stills 3 12.5 30 44.5    # a few frames only, for checking
python docs/presentation/build_video.py --lang es --out outputs/video/CrimsonSnow-1min-ES.mp4   # Spanish
```

Spanish version (Spain-first facts, all captions in Spanish): `outputs/video/CrimsonSnow-1min-ES.mp4`; the voice-over script in Spanish, with timings and sources, is [guion-video-es.md](guion-video-es.md).
