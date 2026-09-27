# experiment_cat

Nav2, SLAM and emcl2 integration for CAT. See the [Japanese operation guide](README.ja.md).

Robot hardware, sensors, TF, manual control and stopping belong to [cat_robot](../cat_robot/README.md). Navigation includes its bringup; do not start the hardware twice.

```bash
ros2 launch experiment_cat navigation.launch.py slam:=false map:=/absolute/path/map.yaml
ros2 launch experiment_cat mapping.launch.py
```

Configuration lives in `config/`: `nav2_params.yaml`, `slam_toolbox.yaml`, `emcl2.yaml`. The scan obstacle height limit is explicitly 0.8 m in both costmaps. Physical robot configuration is owned exclusively by `cat_bringup/config/`.

The navigation guard monitors sensor and localization health. The robot's base_safety selects manual/external commands and owns the driver lease. Arm through `/base_safety/arm`; brake through `/base_safety/brake`. RPM topics are available only in the motor maintenance mode.

Use `navigation_map:=/path/edited.yaml` to separate the Nav2 map from the unmodified `map:=...` (or `localization_map:=...`) used by emcl2. The topics are `/map` and `/localization/map`, respectively. Both maps must use consistent coordinates.

Optionally pass `waypoints_file:=/path/route.yaml` (see `examples/waypoints.yaml`). Loading only displays numbered arrows in RViz. Arm navigation, then call `/waypoint_route/start` with `std_srvs/srv/Trigger`; use `/waypoint_route/cancel` to cancel. No automatic start.

Create routes without a robot using the standalone editor:

```bash
ros2 launch experiment_cat waypoint_editor.launch.py map:=/path/map.yaml output:=/path/route.yaml
ros2 service call /waypoint_editor/save std_srvs/srv/Trigger '{}'
```

Place points in order with RViz **2D Goal Pose**, dragging to set heading. Optional `input:=/path/route.yaml` loads an existing route. Services `/waypoint_editor/undo` and `/waypoint_editor/clear` undo the last point or clear the list. Only `/waypoint_editor/save` writes the file (replacing it if present). The editor starts only a map server, its lifecycle manager, RViz and the editor node; it requires no robot or localization. Navigation retains only loading and following saved routes; `waypoints_output` has been removed.
