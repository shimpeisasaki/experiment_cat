"""Complete LiDAR-based Nav2 bringup for the experiment robot.

With ``slam:=true`` (the default), slam_toolbox publishes map -> odom while
building a map. With ``slam:=false``, pass a saved map YAML path and Nav2
starts separate localization/navigation map servers plus emcl2. In both cases this launch owns the base,
robot description, and RPLIDAR S1; do not start those nodes separately.
"""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, GroupAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node, SetRemap
from launch_ros.substitutions import FindPackageShare


def map_nodes(context):
    """Validate paths before starting hardware and keep localization inputs isolated."""
    slam = LaunchConfiguration('slam').perform(context) == 'true'
    localization = LaunchConfiguration('localization_map').perform(context)
    navigation = LaunchConfiguration('navigation_map').perform(context)
    if not slam and not localization:
        raise ValueError('slam:=false requires map:=... or localization_map:=...')
    if not slam and not navigation:
        navigation = localization
    for value in ([localization] if not slam else []) + ([navigation] if navigation else []):
        if not Path(value).expanduser().is_file():
            raise ValueError(f'Map YAML does not exist: {value}')
    actions = []
    if navigation:
        actions += [
            Node(package='nav2_map_server', executable='map_server', name='map_server',
                 parameters=[{'use_sim_time': False, 'frame_id': 'map',
                              'yaml_filename': str(Path(navigation).expanduser().resolve())}],
                 output='screen'),
            Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                 name='lifecycle_manager_navigation_map',
                 parameters=[{'autostart': True, 'node_names': ['map_server']}], output='screen'),
        ]
    if slam:
        mapper = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare('slam_toolbox'), 'launch', 'online_async_launch.py'])),
            launch_arguments={'use_sim_time': 'false',
                              'slam_params_file': LaunchConfiguration('slam_params_file')}.items())
        # With a written navigation map, live SLAM must not overwrite /map.
        actions.append(GroupAction([SetRemap(src='/map', dst='/localization/map'), mapper])
                       if navigation else mapper)
    else:
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare('experiment_cat'), 'launch', 'localization.launch.py'])),
            launch_arguments={
                'map': str(Path(localization).expanduser().resolve()),
                'use_sim_time': 'false',
                'localization_params_file': LaunchConfiguration('localization_params_file'),
            }.items()))
    return actions


def waypoint_node(context):
    source = LaunchConfiguration('waypoints_file').perform(context)
    output = LaunchConfiguration('waypoints_output').perform(context)
    if not source and not output:
        return []
    if source:
        path = Path(source).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f'Waypoint YAML does not exist: {path}')
        source = str(path)
    return [Node(package='experiment_cat', executable='waypoint_route', name='waypoint_route',
                 parameters=[{'waypoints_file': source, 'waypoints_output': output}], output='screen')]


def generate_launch_description():
    share = FindPackageShare('experiment_cat')
    base_share = FindPackageShare('cat_bringup')
    nav2_share = FindPackageShare('nav2_bringup')
    params_file = LaunchConfiguration('params_file')
    robot_config = LaunchConfiguration('robot_config')
    manual_config = LaunchConfiguration('manual_config')

    return LaunchDescription([
        DeclareLaunchArgument('slam', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('use_gnss', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('gnss_serial', default_value=''),
        DeclareLaunchArgument('serial_number', default_value='10028118'),
        DeclareLaunchArgument('use_zed', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('odom_source', default_value='vio', choices=['vio', 'wheel']),
        DeclareLaunchArgument('zed_config', default_value=PathJoinSubstitution([
            base_share, 'config', PythonExpression(["'zed_vio.yaml' if '",
                LaunchConfiguration('odom_source'), "' == 'vio' else 'zed_sensors.yaml'"])])),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument(
            'map', default_value='',
            description='Localization map YAML (legacy alias). Required when slam:=false.'),
        DeclareLaunchArgument('localization_map', default_value=LaunchConfiguration('map'),
                              description='Unmodified map used only by emcl2.'),
        DeclareLaunchArgument('navigation_map', default_value='',
                              description='Written map for Nav2; defaults to localization map or live SLAM.'),
        DeclareLaunchArgument('waypoints_file', default_value='',
                              description='Optional waypoint YAML; load/display only until ~/start is called.'),
        DeclareLaunchArgument('waypoints_output', default_value='',
                              description='Destination YAML for RViz waypoints; write only on ~/save.'),
        DeclareLaunchArgument('serial_port', default_value='/dev/rplidar'),
        DeclareLaunchArgument('localization_params_file', default_value=PathJoinSubstitution([
            share, 'config', 'emcl2.yaml'])),
        DeclareLaunchArgument(
            'params_file',
            default_value=PathJoinSubstitution([share, 'config', 'nav2_params.yaml'])),
        DeclareLaunchArgument(
            'slam_params_file',
            default_value=PathJoinSubstitution([share, 'config', 'slam_toolbox.yaml'])),
        DeclareLaunchArgument(
            'robot_config',
            default_value=PathJoinSubstitution([base_share, 'config', 'robot.yaml'])),
        DeclareLaunchArgument(
            'manual_config',
            default_value=PathJoinSubstitution([base_share, 'config', 'manual_control.yaml'])),

        OpaqueFunction(function=map_nodes),
        OpaqueFunction(function=waypoint_node),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                base_share, 'launch', 'bringup.launch.py'])),
            launch_arguments={
                'robot_config': robot_config, 'manual_config': manual_config,
                'zed_config': LaunchConfiguration('zed_config'),
                'odom_source': LaunchConfiguration('odom_source'),
                'use_zed': LaunchConfiguration('use_zed'),
                'use_gnss': LaunchConfiguration('use_gnss'),
                'gnss_serial': LaunchConfiguration('gnss_serial'),
                'serial_port': LaunchConfiguration('serial_port'),
                'serial_number': LaunchConfiguration('serial_number'),
                'require_navigation': 'true', 'rviz': 'false',
            }.items()),
        Node(package='experiment_cat', executable='navigation_guard',
             name='navigation_guard', output='screen'),
        Node(package='nav2_collision_monitor', executable='collision_monitor',
             name='collision_monitor', output='screen', parameters=[params_file]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='collision_monitor_lifecycle_manager', output='screen',
             parameters=[{'autostart': True, 'node_names': ['collision_monitor']}]),
        Node(
            package='rviz2', executable='rviz2', name='nav2_rviz', output='screen',
            arguments=['-d', PathJoinSubstitution([
                share, 'rviz', 'navigation.rviz'])],
            condition=IfCondition(LaunchConfiguration('rviz'))),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                nav2_share, 'launch', 'navigation_launch.py'])),
            launch_arguments={
                'use_sim_time': 'false',
                'autostart': 'true',
                'params_file': params_file,
                'use_composition': 'False',
            }.items()),

    ])
