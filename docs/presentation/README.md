# Pitch deck (5 minutes)

[CrimsonSnow-pitch.pptx](CrimsonSnow-pitch.pptx): 9 slides, 4:30 of talk, plus 1 bonus slide. The spoken
script and the time for each slide are in the speaker notes (PowerPoint: View > Notes, or Presenter View).

| # | Slide | For the jury | Time |
|---|---|---|---|
| 1 | CrimsonSnow | who we are, the task in one line | 0:15 |
| 2 | Find the battery, drop it in the box | why: battery fires in Spain's waste plants (utility) | 0:30 |
| 3 | Only the battery, even in a pile of junk | clutter test video: 14 other objects, picked first try | 0:20 |
| 4 | 293 demonstrations, each batch aimed at a failure | data in 4 sessions, each one aimed at what the last model got wrong | 0:40 |
| 5 | How it works: find, grab, drop, check | the pipeline, with automatic retries when the check fails | 0:45 |
| 6 | Our own vision model checks the box | innovation: labels for free from the gripper | 0:45 |
| 7 | The final model, on camera | 4 recorded runs of the final model at 3× speed; 9 of 11 logged attempts on the first run | 0:25 |
| 8 | Built to be repeated — and to demo | `so` helper, CI, control panel; code, data and models public | 0:25 |
| 9 | Live now: five attempts, hands off | the four models: 3/7 → 24/24 → 2 gaps → 9 of 11; live demo | 0:25 |
| 10 | Backup / bonus: CrimsonSnow in 1 minute | Spanish 1-minute video (not timed) | — |

Videos play on click (slide show, or the play button while editing):

- slide 3: [video/clutter_test_2x.mp4](video/clutter_test_2x.mp4), the real clutter test at 2× speed;
- slide 7: [video/final_model_3x.mp4](video/final_model_3x.mp4), four runs of the final model
  (`act_battery_finetune_locations`) filmed by `so demo --record-video` on 22 Nov, 3× speed, each a first-run
  success in `journal/demo.csv`. Rebuild it on the team laptop with
  `python docs/presentation/build_demo_clip.py` (lerobot env: it needs PyAV);
- slide 10: `outputs/video/CrimsonSnow-1min-ES.mp4` (silent; one of us reads the voice-over live), which is not
  in the repository: on a computer without it the slide is left out (the build prints a note).

**For presenting from the team laptop:** `python docs/presentation/build_deck.py --voice` writes
`outputs/presentation/CrimsonSnow-pitch-voz.pptx`, the same deck with the voiced cut on slide 10. It stays in
`outputs/` (git-ignored), so the voice recording never reaches the public repository. With all videos the deck
is about 23 MB.

Rebuild after changing a number (all of them are in `NUMBERS` at the top of the script):

```bash
pip install python-pptx                      # any Python 3.10+, not needed in the lerobot env
python docs/presentation/build_deck.py       # uses the pictures in img/
python docs/presentation/build_deck.py --refresh-images           # copy them again from outputs/ (team laptop)
python docs/presentation/build_deck.py --panel-shot panel.png     # new control-panel screenshot for slide 8
python docs/presentation/build_deck.py --voice                    # the laptop copy with the voiced bonus video
```

The clutter-test pictures (`img/trash_*.jpg`, `img/clutter_poster.jpg`) are stills of
`outputs/demo/test video trash/test.mp4` (22 Nov 2026) and are not refreshed; `img/bonus_es_poster.jpg` is the
silent 1-minute video at 20 s; `img/final_poster.jpg` is the first frame of slide 7's clip.


## Final cut with the team's voice (Spanish)

`outputs/video/CrimsonSnow-1min-ES-voz.mp4`: exactly 60 s, 1920×1080, AAC sound. The four voice-over recordings in `recording/` (kept on the laptop, git-ignored) are trimmed, their pauses shortened, sped up ×1.12 without changing the pitch and levelled to -16 LUFS. Every picture change sits on the word it illustrates (word times measured once with Whisper, listed in `EVENTS`), with the spoken text as subtitles. Rebuild: `python docs/presentation/build_story_video.py`.
