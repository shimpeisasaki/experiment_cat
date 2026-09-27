# experiment_cat

Nav2, SLAM and emcl2 integration for CAT. See the [Japanese operation guide](README.ja.md).

Robot hardware, sensors, TF, manual control and stopping belong to [cat_robot](../cat_robot/README.md). Navigation includes its bringup; do not start the hardware twice.

```bash
ros2 launch experiment_cat navigation.launch.py slam:=false map:=/absolute/path/map.yaml
ros2 launch experiment_cat mapping.launch.py
```

Configuration lives in `config/`: `nav2_params.yaml`, `slam_toolbox.yaml`, `emcl2.yaml`. The scan obstacle height limit is explicitly 0.8 m in both costmaps. Physical robot configuration is owned exclusively by `cat_bringup/config/`.

The navigation guard monitors sensor and localization health. The robot's base_safety selects manual/external commands and owns the driver lease. Arm through `/base_safety/arm`; brake through `/base_safety/brake`. RPM topics are available only in the motor maintenance mode.
