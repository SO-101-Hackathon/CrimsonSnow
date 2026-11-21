# Local camera check: test report

Model `outputs/vision/model/battery_check.pt` (ResNet-18, trained 2026-11-21T20:06:10, epoch 8 of 10, on 3200 frames from ds_af51284a6c).
It answers *in the box* only when at least 80% sure and *on the mat* / *in the gripper* when at least 60% sure; otherwise the demo falls back to the gripper reading.

## Episodes it never saw

800 frames from 50 recorded episodes (every fifth episode, never trained on).

| | frames | right |
|---|---:|---:|
| all frames | 800 | 99.8% |
| arm folded at rest (what the demo sees) | 170 | 100.0% |

What the demo would do: wrong *in the box* (a failed attempt counted as success): **0**; missed *in the box* (one extra run): 0; unsure (falls back to the gripper): 5.

Confusion (rows = truth, columns = answer):

| truth \ answer | in_box | on_mat | in_gripper |
|---|---:|---:|---:|
| in_box | 300 | 0 | 0 |
| on_mat | 0 | 299 | 1 |
| in_gripper | 1 | 0 | 199 |

## Real check photos from `so demo` runs

Taken by `so demo` after real runs on 21 Nov 2026 (labelled by eye). In some a person's hand is in the picture: the recordings never show hands, so those are harder than a real demo.

| photo | truth | hands | answer | probabilities |
|---|---|---|---|---|
| 20261121_155735/attempt01_run1_top | in_gripper |  | in_gripper | in the gripper 97%, on the mat 2%, in the box 1% |
| 20261121_160918/attempt01_run1_top | on_mat |  | on_mat | on the mat 85%, in the gripper 13%, in the box 2% |
| 20261121_160918/attempt01_run2_top | in_box |  | in_box | in the box 82%, in the gripper 14%, on the mat 4% |
| 20261121_160918/attempt02_run1_top | in_box |  | in_box | in the box 90%, in the gripper 7%, on the mat 3% |
| 20261121_160918/attempt03_run1_top | on_mat | yes | on_mat | on the mat 90%, in the gripper 8%, in the box 3% |
| 20261121_160918/attempt03_run2_top | on_mat |  | on_mat | on the mat 94%, in the gripper 5%, in the box 1% |
| 20261121_160918/attempt03_run3_top | in_box | yes | unsure ✗ | in the box 69%, in the gripper 21%, on the mat 10% |
| 20261121_160918/attempt04_run1_top | hidden | yes | unsure | in the gripper 51%, on the mat 47%, in the box 2% |
| 20261121_160918/attempt04_run2_top | on_mat |  | on_mat | on the mat 96%, in the gripper 3%, in the box 1% |
| 20261121_160918/attempt04_run3_top | elsewhere | yes | on_mat | on the mat 74%, in the gripper 24%, in the box 3% |
| 20261121_160918/attempt05_run1_top | on_mat | yes | on_mat | on the mat 90%, in the gripper 8%, in the box 2% |
| 20261121_160918/attempt05_run2_top | elsewhere | yes | unsure | in the gripper 56%, in the box 31%, on the mat 13% |
| 20261121_161706/attempt01_run1_top | on_mat | yes | on_mat | on the mat 82%, in the gripper 14%, in the box 5% |
| 20261121_161706/attempt01_run2_top | on_mat | yes | on_mat | on the mat 70%, in the gripper 25%, in the box 5% |
| 20261121_161706/attempt02_run1_top | on_mat |  | on_mat | on the mat 86%, in the gripper 13%, in the box 2% |
| 20261121_162022/attempt01_run1_top | on_mat |  | on_mat | on the mat 75%, in the gripper 24%, in the box 1% |
| 20261121_162022/attempt01_run2_top | on_mat |  | on_mat | on the mat 76%, in the gripper 22%, in the box 1% |
| 20261121_162022/attempt01_run3_top | on_mat |  | on_mat | on the mat 75%, in the gripper 23%, in the box 1% |

*elsewhere* / *hidden*: the battery is not in the box, so any answer but *in the box* is fine.

Without hands: 10/10 right. With a hand in the picture: 7/8 right (3 unsure, which falls back to the gripper). Wrong *in the box* answers: **0**.

Sample answers on unseen episodes: `outputs/vision/samples.jpg`.

## Speed

11 ms per photo on NVIDIA GeForce RTX 4060 Laptop GPU (the online checks took about 1-3 s).

