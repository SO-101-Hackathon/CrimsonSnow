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
