"""Bring up the robot once; joystick A captures a stopped, stepped 360-degree scan."""
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('experiment_cat')
    base = FindPackageShare('cat_bringup')
    return LaunchDescription([
        DeclareLaunchArgument('output_dir', default_value=str(Path.home()/'ros2_ws/data/panorama')),
        DeclareLaunchArgument('bringup', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('odom_source', default_value='vio', choices=['vio', 'wheel']),
        DeclareLaunchArgument('serial_number', default_value='10028118'),
        DeclareLaunchArgument('zed_log_level', default_value='warn',
                              choices=['debug', 'info', 'warn', 'error', 'fatal']),
        DeclareLaunchArgument('steps', default_value='12', description='12 captures at 30-degree intervals'),
        DeclareLaunchArgument('angular_speed', default_value='0.18', description='Maximum turn speed, rad/s; known working 24-step profile'),
        DeclareLaunchArgument('minimum_angular_speed', default_value='0.0', description='Optional minimum turn command, rad/s; zero permits precise settling'),
        DeclareLaunchArgument('settle_time', default_value='0.5'),
        DeclareLaunchArgument('width', default_value='2048'),
        DeclareLaunchArgument('height', default_value='1024'),
        DeclareLaunchArgument('save_frames', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('start_button', default_value='0', description='Matches base_safety A index'),
        DeclareLaunchArgument('robot_config', default_value=PathJoinSubstitution([base, 'config', 'robot.yaml'])),
        DeclareLaunchArgument('zed_config', default_value=PathJoinSubstitution([share, 'config', 'zed_panorama.yaml'])),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([base, 'launch', 'bringup.launch.py'])),
            condition=IfCondition(LaunchConfiguration('bringup')),
            launch_arguments={
                'odom_source': LaunchConfiguration('odom_source'),
                'serial_number': LaunchConfiguration('serial_number'),
                'robot_config': LaunchConfiguration('robot_config'),
                'zed_config': LaunchConfiguration('zed_config'),
                'zed_log_level': LaunchConfiguration('zed_log_level'),
                'navigation_button': LaunchConfiguration('start_button'),
                'use_lidar': 'false', 'rviz': 'false', 'require_navigation': 'false',
                'use_base': 'true', 'use_zed': 'true', 'enable_joystick': 'true',
            }.items()),
        Node(package='cat_panorama', executable='panorama_capture', output='screen',
             parameters=[{
                 'output_dir': LaunchConfiguration('output_dir'),
                 'width': ParameterValue(LaunchConfiguration('width'), value_type=int),
                 'height': ParameterValue(LaunchConfiguration('height'), value_type=int),
                 'save_frames': ParameterValue(LaunchConfiguration('save_frames'), value_type=bool),
             }], additional_env={'PYTHONNOUSERSITE': '1'}),
        Node(package='experiment_cat', executable='panorama_rotate', output='screen',
             parameters=[{
                 'steps': ParameterValue(LaunchConfiguration('steps'), value_type=int),
                 'angular_speed': ParameterValue(LaunchConfiguration('angular_speed'), value_type=float),
                 'minimum_angular_speed': ParameterValue(LaunchConfiguration('minimum_angular_speed'), value_type=float),
                 'settle_time': ParameterValue(LaunchConfiguration('settle_time'), value_type=float),
                 'start_button': ParameterValue(LaunchConfiguration('start_button'), value_type=int),
             }], additional_env={'PYTHONNOUSERSITE': '1'}),
    ])
