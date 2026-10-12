"""Run the image-only d1 ground evaluation experiment."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('image_topic', default_value='/zed/zed_node/rgb/color/rect/image'),
        DeclareLaunchArgument('server', default_value='http://127.0.0.1:8080'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(package='experiment_cat', executable='d1_ground_eval', name='d1_ground_eval',
             output='screen', parameters=[{
                 'image_topic': LaunchConfiguration('image_topic'),
                 'server': LaunchConfiguration('server'),
                 'use_sim_time': LaunchConfiguration('use_sim_time'),
             }]),
    ])
