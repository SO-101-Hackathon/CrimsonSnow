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

## 2026-11-21 22:29:49  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 3m42s

## 2026-11-21 22:34:17  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 5m29s

## 2026-11-21 22:40:09  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

## 2026-11-21 22:46:30  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 1 after 19s

## 2026-11-21 22:47:31  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 1 after 18s

## 2026-11-21 22:52:25  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 1 after 1m06s

## 2026-11-21 22:53:36  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 1 after 52s

## 2026-11-21 22:57:47  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 10m30s

## 2026-11-21 23:10:29  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 5m41s

## 2026-11-21 23:17:26  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=20 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 1m05s

## 2026-11-21 23:18:35  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=20 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 3m43s

## 2026-11-21 23:22:23  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=20 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=battery sample' \
  --duration=30 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 2m06s

## 2026-11-21 23:25:13  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 1m40s

## 2026-11-21 23:26:56  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 1m16s

## 2026-11-21 23:31:02  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=24 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 1 after 5m26s

## 2026-11-21 23:41:25  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=25 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 6m17s

## 2026-11-21 23:47:48  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=25 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 1 after 6m36s

## 2026-11-21 23:55:50  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=25 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 17m24s

## 2026-11-22 00:14:13  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

## 2026-11-22 00:17:23  demo sensecraft:battery final dataset - ACT

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  '--label=sensecraft:battery final dataset - ACT' \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\AppData\Roaming\SenseCraft Robotics\backend-storage\projects\proj_0de5a2ce\models\cloud_local_8eaea7cea8f9_artifact\bundle\checkpoints\last\pretrained_model' \
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

exit code 0 after 1m05s

## 2026-11-22 03:15:39  demo act_battery_finetune_15k@015000

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=act_battery_finetune_15k@015000 \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  '--policy.path=~\Desktop\H\outputs\train\act_battery_finetune_15k\checkpoints\015000\pretrained_model' \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 4m36s

## 2026-11-22 03:21:00  demo outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

## 2026-11-22 03:21:37  demo outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 5m45s

## 2026-11-22 03:27:43  demo outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 1m50s

## 2026-11-22 03:29:41  demo outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 1m43s

## 2026-11-22 03:31:36  demo outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_15k/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 1m48s

## 2026-11-22 03:35:09  demo outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 8m07s

## 2026-11-22 03:43:48  demo outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 1 after 3m16s

## 2026-11-22 03:47:30  demo outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 7m29s

## 2026-11-22 03:55:06  demo outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_full_100k_cloud/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 6m59s

## 2026-11-22 05:02:45  demo outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 1 after 3m01s

## 2026-11-22 05:05:51  demo outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 1 after 4m17s

## 2026-11-22 05:10:21  demo outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --record-video \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 1 after 2m58s

## 2026-11-22 05:17:33  demo outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model

```bash
python \
  -m \
  sokit.demo \
  --tries=3 \
  --attempts=5 \
  --check=auto \
  --label=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --scene-camera=top \
  --wrist-camera=wrist \
  -- \
  --strategy.type=base \
  --policy.path=outputs/train/act_battery_finetune_locations/checkpoints/last/pretrained_model \
  --robot.type=so101_follower \
  --robot.port=COM5 \
  --robot.id=so100_follower \
  '--robot.cameras={ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG} }' \
  '--robot.calibration_dir=~/AppData/Roaming/SenseCraft Robotics/backend-storage/calibration/lerobot/robots/so_follower' \
  '--task=Put the TNT in the bin' \
  --duration=40 \
  --interactive=true \
  --play_sounds=false \
  '--rename_map={observation.images.top: observation.images.front, observation.images.wrist: observation.images.gripper}'
```

exit code 0 after 6m01s
