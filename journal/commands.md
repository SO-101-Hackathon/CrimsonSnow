# Command journal

Every hardware / training command run through `so`, in order. This is the raw
material for the README's reproduction steps and for the jury's questions.

## 2026-11-20 18:01:21  calibrate follower

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B910297241 \
  --robot.id=crimson_follower
```

exit code -2 after 16s

## 2026-11-20 18:01:38  calibrate leader

```bash
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5B910312701 \
  --teleop.id=crimson_leader
```

exit code -2 after 7s

## 2026-11-20 18:07:12  calibrate follower

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B910297241 \
  --robot.id=crimson_follower
```

exit code 0 after 1m14s

## 2026-11-20 18:08:36  calibrate leader

```bash
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5B910312701 \
  --teleop.id=crimson_leader
```

exit code 1 after 25s

## 2026-11-20 18:15:58  calibrate follower

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B910297241 \
  --robot.id=crimson_follower
```

exit code 0 after 12s

## 2026-11-20 18:16:15  calibrate follower

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B910297241 \
  --robot.id=crimson_follower
```

exit code -2 after 2m06s

## 2026-11-20 18:18:23  calibrate follower

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B910297241 \
  --robot.id=crimson_follower
```

exit code -2 after 7s

## 2026-11-20 18:18:35  calibrate follower

```bash
lerobot-calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B910297241 \
  --robot.id=crimson_follower
```

exit code 0 after 1m40s

## 2026-11-20 18:21:19  calibrate leader

```bash
lerobot-calibrate \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5B910312701 \
  --teleop.id=crimson_leader
```

exit code 0 after 1m29s

## 2026-11-21 15:56:41  demo sensecraft:battery sample - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --model=claude-opus-5-5 \
  '--label=sensecraft:battery sample - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_20d497174674_artifact\bundle\checkpoints\last\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=battery sample' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 2m47s

## 2026-11-21 16:08:47  demo sensecraft:battery sample - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery sample - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_20d497174674_artifact\bundle\checkpoints\last\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=battery sample' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 7m47s

## 2026-11-21 16:16:39  demo sensecraft:battery sample - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery sample - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_20d497174674_artifact\bundle\checkpoints\last\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=battery sample' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 3m13s

## 2026-11-21 16:19:57  demo sensecraft:battery sample - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery sample - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_20d497174674_artifact\bundle\checkpoints\last\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=battery sample' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 3m24s

## 2026-11-21 16:30:54  try sensecraft:battery sample - ACT

```bash
python \
  -m \
  sokit.demo \
  --manual \
  '--label=sensecraft:battery sample - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_20d497174674_artifact\bundle\checkpoints\last\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=battery sample' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 6m30s

## 2026-11-21 20:07:47  vision test

```bash
python \
  -m \
  sokit.vision \
  test
```

exit code 0 after 14s

## 2026-11-21 20:10:59  vision check

```bash
python \
  -m \
  sokit.vision \
  check \
  outputs/demo/20261121_160918/attempt02_run1_top.jpg \
  outputs/demo/20261121_162022/attempt01_run1_top.jpg
```

exit code 0 after 6s
