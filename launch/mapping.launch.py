"""Build a 2D map manually with the curvature joystick and RPLIDAR S1.

cat_bringup owns manual control. slam_toolbox owns map -> odom.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('experiment_cat')
    base_share = FindPackageShare('cat_bringup')
    nav2_share = FindPackageShare('nav2_bringup')

    return LaunchDescription([
        DeclareLaunchArgument('use_gnss', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('gnss_serial', default_value=''),
        DeclareLaunchArgument('serial_port', default_value='/dev/rplidar'),
        DeclareLaunchArgument('use_zed', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('odom_source', default_value='vio', choices=['vio', 'wheel']),
        DeclareLaunchArgument('mapping_rviz', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('serial_number', default_value='10028118'),
        DeclareLaunchArgument('log_level', default_value='warn',
                              choices=['debug', 'info', 'warn', 'error', 'fatal']),
        DeclareLaunchArgument('zed_log_level', default_value=LaunchConfiguration('log_level')),
        DeclareLaunchArgument(
            'robot_config',
            default_value=PathJoinSubstitution([base_share, 'config', 'robot.yaml'])),
        DeclareLaunchArgument(
            'manual_config',
            default_value=PathJoinSubstitution([base_share, 'config', 'manual_control.yaml'])),
        DeclareLaunchArgument(
            'zed_config',
            default_value=PathJoinSubstitution([base_share, 'config', PythonExpression([
                "'zed_vio.yaml' if '", LaunchConfiguration('odom_source'),
                "' == 'vio' else 'zed_sensors.yaml'"])])),
        DeclareLaunchArgument(
            'slam_params_file',
            default_value=PathJoinSubstitution([share, 'config', 'slam_toolbox.yaml'])),

        # This owns the base, robot_state_publisher, RPLIDAR, joy, curvature
        # teleop, and the manual velocity smoother. Its RViz is disabled in
        # favor of Nav2's map-oriented RViz configuration below.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                base_share, 'launch', 'bringup.launch.py'])),
            launch_arguments={
                'use_base': 'true',
                'use_gnss': LaunchConfiguration('use_gnss'),
                'gnss_serial': LaunchConfiguration('gnss_serial'),
                'serial_port': LaunchConfiguration('serial_port'),
                'odom_source': LaunchConfiguration('odom_source'),
                'use_lidar': 'true',
                'use_zed': LaunchConfiguration('use_zed'),
                'rviz': 'false',
                'enable_joystick': 'true',
                'serial_number': LaunchConfiguration('serial_number'),
                'robot_config': LaunchConfiguration('robot_config'),
                'manual_config': LaunchConfiguration('manual_config'),
                'zed_config': LaunchConfiguration('zed_config'),
                'log_level': LaunchConfiguration('log_level'),
                'zed_log_level': LaunchConfiguration('zed_log_level'),
            }.items()),
        Node(package='slam_toolbox', executable='async_slam_toolbox_node',
             name='slam_toolbox', output='screen',
             parameters=[LaunchConfiguration('slam_params_file'), {'use_sim_time': False}],
             arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')]),
        Node(
            package='rviz2', executable='rviz2', name='mapping_rviz', output='screen',
            arguments=['-d', PathJoinSubstitution([
                nav2_share, 'rviz', 'nav2_default_view.rviz']),
                '--ros-args', '--log-level', LaunchConfiguration('log_level')],
            condition=IfCondition(LaunchConfiguration('mapping_rviz'))),
    ])
