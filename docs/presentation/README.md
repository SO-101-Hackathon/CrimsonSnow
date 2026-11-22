# Pitch deck (5 minutes)

[CrimsonSnow-pitch.pptx](CrimsonSnow-pitch.pptx): 8 slides, 4:10 of talk, plus 1 backup slide. The spoken
script and the time for each slide are in the speaker notes (PowerPoint: View > Notes, or Presenter View).

| # | Slide | For the jury | Time |
|---|---|---|---|
| 1 | CrimsonSnow | who we are, the task in one line | 0:15 |
| 2 | Find the battery, drop it in the box | why: battery fires in Spain's waste plants (utility) | 0:30 |
| 3 | Only the battery, even in a pile of junk | clutter test video: 14 other objects, picked first try | 0:20 |
| 4 | 257 demonstrations, aimed at our failures | data, iteration on failures | 0:45 |
| 5 | How it works: find, grab, drop, check | the pipeline, with automatic retries when the check fails | 0:45 |
| 6 | Our own vision model checks the box | innovation: labels for free from the gripper | 0:45 |
| 7 | Built to be repeated | `so` helper, CI, control panel, open repo | 0:25 |
| 8 | Live now: five attempts, hands off | 3/7 by hand → 24/24, 34 logged runs, live demo | 0:25 |
| 9 | Backup / bonus: CrimsonSnow in 1 minute | Spanish 1-minute video, voice-over live (not timed) | — |

Videos play on click (slide show, or the play button while editing). Slide 3 embeds
[video/clutter_test_2x.mp4](video/clutter_test_2x.mp4) (the real clutter test at 2× speed). Slide 9 embeds
`outputs/video/CrimsonSnow-1min-ES.mp4`, which is not in the repository: on a computer without it the slide
is left out (the build prints a note). The English version is `outputs/video/CrimsonSnow-1min.mp4`.
With both videos the deck is about 18 MB.

Rebuild after changing a number (all of them are in `NUMBERS` at the top of the script):

```bash
pip install python-pptx                      # any Python 3.10+, not needed in the lerobot env
python docs/presentation/build_deck.py       # uses the pictures in img/
python docs/presentation/build_deck.py --refresh-images           # copy them again from outputs/ (team laptop)
python docs/presentation/build_deck.py --panel-shot panel.png     # new control-panel screenshot for slide 7
```

The clutter-test pictures (`img/trash_*.jpg`, `img/clutter_poster.jpg`) are stills of
`outputs/demo/test video trash/test.mp4` (22 Nov 2026) and are not refreshed; `img/bonus_es_poster.jpg` is the
1-minute video at 20 s.


## Final cut with the team's voice (Spanish)

`outputs/video/CrimsonSnow-1min-ES-voz.mp4`: exactly 60 s, 1920×1080, AAC sound. The four voice-over recordings in `recording/` (kept on the laptop, git-ignored) are trimmed, their pauses shortened, sped up ×1.12 without changing the pitch and levelled to -16 LUFS. Every picture change sits on the word it illustrates (word times measured once with Whisper, listed in `EVENTS`), with the spoken text as subtitles. Rebuild: `python docs/presentation/build_story_video.py`.
