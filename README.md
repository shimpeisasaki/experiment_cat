# experiment_cat

Nav2, SLAM and emcl2 integration for CAT. See the [Japanese operation guide](README.ja.md).

Robot hardware, sensors, TF, manual control and stopping belong to [cat_robot](../cat_robot/README.md). Navigation includes its bringup; do not start the hardware twice.

```bash
ros2 launch experiment_cat navigation.launch.py
ros2 launch experiment_cat mapping.launch.py
```

Configuration lives in `config/`: `nav2_params.yaml`, `slam_toolbox.yaml`, `emcl2.yaml`. The scan obstacle height limit is explicitly 0.8 m in both costmaps. Physical robot configuration is owned exclusively by `cat_bringup/config/`.

The navigation guard monitors sensor and localization health. The robot's base_safety selects manual/external commands and owns the driver lease. Arm through `/base_safety/arm`; brake through `/base_safety/brake`. RPM topics are available only in the motor maintenance mode.

Navigation defaults to the saved localization map `map/19F_260928.yaml`, the edited Nav2 map `map/19F_260928_Nav_2.yaml`, and `map/19F_waypoint.yaml`. Set `slam:=true` to use live SLAM instead. The topics are `/localization/map` and `/map`; both maps and waypoints must share coordinates.

The default route is `/home/uedalab/ros2_ws/map/19F_waypoint.yaml`; override it with `waypoints_file:=/path/route.yaml`. Loading only displays numbered arrows in RViz. Arm navigation, then call `/waypoint_route/start` with `std_srvs/srv/Trigger`; use `/waypoint_route/cancel` to cancel. No automatic start.

Create routes without a robot using the standalone editor:

```bash
ros2 launch experiment_cat waypoint_editor.launch.py
ros2 service call /waypoint_editor/save std_srvs/srv/Trigger '{}'
```

The editor defaults to the Nav2 map `map/19F_260928_Nav_2.yaml` and loads/saves `map/19F_waypoint.yaml`. Place points in order with RViz **2D Goal Pose**, dragging to set heading. Services `/waypoint_editor/undo` and `/waypoint_editor/clear` undo the last point or clear the list. Only `/waypoint_editor/save` writes the file (replacing it if present). The editor starts only a map server, its lifecycle manager, RViz and the editor node; it requires no robot or localization. Navigation retains only loading and following saved routes; `waypoints_output` has been removed.
