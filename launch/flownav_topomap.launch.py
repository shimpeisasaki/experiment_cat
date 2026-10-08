"""Manually drive and record the selected ZED lens for a FlowNav image route."""
import os
import sys
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def start(context):
    value = lambda name: LaunchConfiguration(name).perform(context)
    lens = value('lens')
    if lens not in ('left', 'right'):
        raise ValueError('lens must be left|right')
    repo = Path(value('flownav_repo')).expanduser().resolve()
    if not (repo / 'deployment/src/navigation/create_topomap.py').is_file():
        raise ValueError(f'FlowNav source missing: {repo}')
    base_share = Path(get_package_share_directory('cat_bringup'))
    image_topic = f'/zed/zed_node/{lens}/color/rect/image/compressed'
    env = {
        'FLOWNAV_IMAGE_TOPIC': image_topic,
        'PYTHONPATH': os.pathsep.join((str(repo / 'deployment/src'),
                                     os.environ.get('PYTHONPATH', ''))),
    }
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(base_share / 'launch/bringup.launch.py')),
            launch_arguments={'use_lidar': 'false', 'require_navigation': 'false',
                              'odom_source': value('odom_source'), 'rviz': 'false',
                              'serial_number': value('serial_number'),
                              'zed_config': str(base_share / 'config/zed_flownav.yaml')}.items()),
        ExecuteProcess(
            cmd=[sys.executable, str(repo / 'deployment/src/navigation/create_topomap.py'),
                 '--dir', value('topomap'), '--dt', value('image_interval')],
            cwd=str(repo / 'deployment/src/navigation'), additional_env=env,
            output='screen'),
    ]


def generate_launch_description():
    workspace = Path('/home/uedalab/ros2_ws')
    return LaunchDescription([
        DeclareLaunchArgument('lens', default_value='left', choices=['left', 'right']),
        DeclareLaunchArgument('odom_source', default_value='vio', choices=['vio', 'wheel']),
        DeclareLaunchArgument('flownav_repo', default_value=str(workspace / 'src/flownav')),
        DeclareLaunchArgument('topomap', default_value=str(workspace / 'data/flownav/topomaps/default')),
        DeclareLaunchArgument('image_interval', default_value='1.0'),
        DeclareLaunchArgument('serial_number', default_value='10028118'),
        OpaqueFunction(function=start),
    ])
