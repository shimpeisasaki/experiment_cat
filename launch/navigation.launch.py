"""Complete LiDAR-based Nav2 bringup for the experiment robot.

With ``slam:=true`` (the default), slam_toolbox publishes map -> odom while
building a map. With ``slam:=false``, pass a saved map YAML path and Nav2
starts map_server + emcl2 instead. In both cases this launch owns the base,
robot description, and RPLIDAR S1; do not start those nodes separately.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('experiment_cat')
    base_share = FindPackageShare('cat_bringup')
    nav2_share = FindPackageShare('nav2_bringup')
    slam_share = FindPackageShare('slam_toolbox')
    params_file = LaunchConfiguration('params_file')
    robot_config = LaunchConfiguration('robot_config')
    manual_config = LaunchConfiguration('manual_config')
    slam = LaunchConfiguration('slam')

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
            description='Saved map YAML. Required when slam:=false.'),
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

        # Mapping mode: slam_toolbox supplies map -> odom, then Nav2 supplies
        # planning, control, recovery behaviors, and LiDAR costmaps.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                slam_share, 'launch', 'online_async_launch.py'])),
            condition=IfCondition(slam),
            launch_arguments={
                'use_sim_time': 'false',
                'slam_params_file': LaunchConfiguration('slam_params_file'),
            }.items()),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                nav2_share, 'launch', 'navigation_launch.py'])),
            launch_arguments={
                'use_sim_time': 'false',
                'autostart': 'true',
                'params_file': params_file,
                'use_composition': 'False',
            }.items()),

        # Saved-map mode: emcl2 is the sole owner of map -> odom.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                share, 'launch', 'localization.launch.py'])),
            condition=UnlessCondition(slam),
            launch_arguments={
                'map': LaunchConfiguration('map'),
                'use_sim_time': 'false',
                'localization_params_file': LaunchConfiguration('localization_params_file'),
            }.items()),
    ])
