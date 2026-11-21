# Pitch deck (5 minutes)

[CrimsonSnow-pitch.pptx](CrimsonSnow-pitch.pptx): 8 slides, 4:40 of talk. The spoken script and the
time for each slide are in the speaker notes (PowerPoint: View > Notes, or Presenter View).

| # | Slide | For the jury | Time |
|---|---|---|---|
| 1 | CrimsonSnow | who we are, the task in one line | 0:15 |
| 2 | Find the battery, drop it in the box | the task and why it matters (utility) | 0:35 |
| 3 | 257 demonstrations, aimed at our failures | data, iteration on failures | 0:50 |
| 4 | ACT: 100,000 steps on an RTX 5090 | the policy and its training | 0:30 |
| 5 | If it fails, it tries again | closed loop with automatic retries | 0:45 |
| 6 | Our own vision model checks the box | innovation: labels for free from the gripper | 0:50 |
| 7 | Built to be repeated | `so` helper, CI, control panel, open repo | 0:25 |
| 8 | Live now: five attempts, hands off | results so far, hand-over to the live demo | 0:30 |

Rebuild after changing a number (all of them are in `NUMBERS` at the top of the script):

```bash
pip install python-pptx                      # any Python 3.10+, not needed in the lerobot env
python docs/presentation/build_deck.py       # uses the pictures in img/
python docs/presentation/build_deck.py --refresh-images           # copy them again from outputs/ (team laptop)
python docs/presentation/build_deck.py --panel-shot panel.png     # new control-panel screenshot for slide 7
```
