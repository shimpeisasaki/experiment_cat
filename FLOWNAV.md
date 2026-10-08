# FlowNav on CAT

FlowNav uses one rectified ZED Mini image (left or right). The ZED may still use
both eyes internally for VIO. Both driving modes use `/odom`, Nav2 `FollowPath`
and Nav2 velocity smoothing; `hybrid` additionally uses `/scan` in the local
costmap and Collision Monitor. Neither mode needs a 2D occupancy map.

## Setup

The default FlowNav checkpoint is
`models/flownav/flownav_weights.pth` relative to the workspace. The separate
Depth Anything checkpoint is only read by FlowNav's training code; the
deployment checkpoint already contains depth encoder tensors.

The configured Python environment is `src/flownav/.venv`. It uses ROS 2's
system packages while keeping NumPy 1.26 and the FlowNav packages local to
the venv. Setup is already complete on this workspace. To recreate it, run
these commands from the workspace root:

```bash
python3 -m venv --system-site-packages src/flownav/.venv
FLOWNAV_PY=src/flownav/.venv/bin/python
"$FLOWNAV_PY" -m pip install 'numpy==1.26.4' 'torchdiffeq==0.2.5' \
  'efficientnet-pytorch==0.7.1' 'diffusers==0.11.1' \
  'huggingface-hub==0.25.2' 'einops==0.8.1' 'wandb==0.21.1' 'scipy==1.15.3'
"$FLOWNAV_PY" -m pip install --no-deps \
  'git+https://github.com/debOliveira/depth-anything-V2.git@7885bbc0647bc64d55ff5803561ea2c7dea1af72' \
  'git+https://github.com/debOliveira/diffusion_policy.git@db1434cc256b53deb0ad7228c129c0ce7c733822'
"$FLOWNAV_PY" -m pip install --no-deps --no-build-isolation -e src/flownav
colcon build --symlink-install --packages-select cat_bringup experiment_cat
source install/setup.bash
```

Check the chosen Python environment before driving:

```bash
src/flownav/.venv/bin/python -c 'import rclpy, torch, torchdiffeq, depth_anything_v2, diffusion_policy, diffusers'
```
The model path, Python executable, topomap and scale are launch arguments.

## Record a route

```bash
ros2 launch experiment_cat flownav_topomap.launch.py lens:=left
```

Use joystick X/manual mode to drive the route. Stop and close the launch at the
destination. Images are written to
`data/flownav/topomaps/default` under the workspace. Recording refuses to overwrite a
nonempty directory. For the right eye, use `lens:=right` and a different
`topomap:=...` directory; use the same lens and directory while navigating.

## Navigate

```bash
ros2 launch experiment_cat flownav_navigation.launch.py mode:=normal lens:=left
```

The default `topomap` is `data/flownav/topomaps/default`, and `goal_node:=-1`
selects its last numbered image. Use `goal_node:=40` to stop near image
`40.png` instead. Start near `0.png` and follow the recording direction. The
goal is an image in the route, not a metric pose. The model must also estimate
that the goal image is close before declaring arrival.

To use an image placed in `data/flownav/goal` under the workspace, pass its
path instead of `goal_node`:

```bash
ros2 launch experiment_cat flownav_navigation.launch.py mode:=normal lens:=left goal_image:="$(pwd)/data/flownav/goal/target.png"
```

With `task:=navigate`, `goal_image` is appended in memory after the recorded
route; the original topomap is not changed. Use this when the destination is
reachable from the end of that route.

To search without a topomap, run exploration with the same image:

```bash
ros2 launch experiment_cat flownav_navigation.launch.py task:=explore mode:=normal lens:=left goal_image:="$(pwd)/data/flownav/goal/target.png"
```

The robot explores without conditioning on the image while the model predicts
that the image is far away. After three consecutive close estimates, it uses
the image to guide its actions. After three consecutive arrival estimates, it
stops the Nav2 controller. `goal_detect_threshold` (default `5.0`) and
`goal_threshold` (default `1.0`) are predicted temporal distances and can be
set as launch arguments. These estimates do not guarantee recognition of a
previously unseen place; exploration can miss it or mistake a similar view for
the target. Test with a nearby, known goal first and keep the joystick brake
available.

Use `mode:=hybrid` for LiDAR obstacle avoidance and collision monitoring.
For goal-agnostic exploration without a topomap, use `task:=explore` without
`goal_image`. It continues until the operator presses B or brakes the robot.
The robot starts braked. Check `/navigation/ready`, the image and `/scan`
(hybrid), then press joystick A or call `/base_safety/arm`. B or
`/base_safety/brake` stops it. Do not run the existing map-based navigation
launch at the same time.

`meters_per_unit` converts FlowNav's normalized action coordinates to meters.
The initial value `0.10` is a low-speed starting estimate, not a measured
calibration. Inspect `/flownav/reference_path` relative to `/odom` in RViz
before arming, and adjust this parameter if the path length is wrong. The
controller is limited to 0.20 m/s; both modes stop when image, inference or
odom becomes stale, and hybrid also stops on stale scan. Normal mode has no
LiDAR-based obstacle avoidance.
