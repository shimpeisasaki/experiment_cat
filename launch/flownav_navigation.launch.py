"""FlowNav image route -> mapless Nav2 controller; optional LiDAR safety."""
import os
import subprocess
import time
from pathlib import Path

from PIL import Image
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def start(context):
    value = lambda name: LaunchConfiguration(name).perform(context)
    mode, lens, task = value('mode'), value('lens'), value('task')
    if mode not in ('normal', 'hybrid') or lens not in ('left', 'right') or task not in ('navigate', 'explore'):
        raise ValueError('mode must be normal|hybrid, lens left|right and task navigate|explore')
    hybrid = mode == 'hybrid'
    repo = Path(value('flownav_repo')).expanduser().resolve()
    ckpt = Path(value('model_ckpt')).expanduser().resolve()
    topomap = Path(value('topomap')).expanduser().resolve()
    script = (repo / 'deployment/src/navigation/navigate.py' if task == 'navigate'
              else repo / 'deployment/src/exploration/explore.py')
    if not script.is_file():
        raise ValueError(f'FlowNav source missing: {repo}')
    if not ckpt.is_file():
        raise ValueError(f'FlowNav checkpoint missing: {ckpt}')
    if task == 'navigate':
        images = list(topomap.glob('*.png')) if topomap.is_dir() else []
        if not images:
            raise ValueError(f'Topomap PNG images missing: {topomap}')
        goal_node = int(value('goal_node'))
        if not -1 <= goal_node < len(images):
            raise ValueError(f'goal_node must be -1 or 0..{len(images) - 1}')
    goal_image_arg = value('goal_image').strip()
    if goal_image_arg:
        if task == 'navigate' and goal_node != -1:
            raise ValueError('Specify either goal_image or goal_node, not both')
        goal_image = Path(goal_image_arg).expanduser().resolve()
        if not goal_image.is_file():
            raise ValueError(f'Goal image missing: {goal_image}')
        try:
            with Image.open(goal_image) as image:
                image.verify()
        except Exception as exc:
            raise ValueError(f'Goal image cannot be read: {goal_image}') from exc
    image_topic = f'/zed/zed_node/{lens}/color/rect/image/compressed'
    lens_frame = f'zed_{lens}_camera_frame'
    share = Path(get_package_share_directory('experiment_cat'))
    base_share = Path(get_package_share_directory('cat_bringup'))
    params = share / 'config' / ('flownav_nav2_hybrid.yaml' if hybrid else 'flownav_nav2.yaml')
    env = {
        'FLOWNAV_NAMESPACE': '/flownav',
        'FLOWNAV_IMAGE_TOPIC': image_topic,
        'PYTHONPATH': os.pathsep.join((str(repo), str(repo / 'deployment/src'),
                                     os.environ.get('PYTHONPATH', ''))),
    }
    python_env = os.environ.copy()
    python_env.update(env)
    check = subprocess.run(
        [value('python_executable'), '-c',
         'import rclpy, cv2, torch, torchdiffeq, depth_anything_v2, '
         'diffusion_policy, efficientnet_pytorch, diffusers, flownav'],
        env=python_env, capture_output=True, text=True, timeout=30)
    if check.returncode:
        raise RuntimeError('FlowNav Python dependencies are missing: ' + check.stderr[-1200:])
    smoother_output = '/flownav/cmd_vel_smoothed' if hybrid else '/cmd_vel_external'
    inference_args = ['--model', 'flownav', '--ckpt', str(ckpt)]
    if task == 'navigate':
        inference_args += ['--dir', str(topomap), '--goal-node', str(goal_node),
                           '--exp_dir', value('log_dir')]
        if goal_image_arg:
            inference_args += ['--goal-image', str(goal_image)]
    else:
        inference_args += ['--dir', 'explore', '--exp_dir',
                           str(Path(value('log_dir')) / ('explore_' + time.strftime('%Y%m%d_%H%M%S')))]
        if goal_image_arg:
            inference_args += ['--goal-image', str(goal_image),
                               '--goal-detect-threshold', value('goal_detect_threshold'),
                               '--goal-threshold', value('goal_threshold')]
    actions = [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(base_share / 'launch/bringup.launch.py')),
            launch_arguments={
                'use_lidar': 'true' if hybrid else 'false',
                'require_navigation': 'true',
                'odom_source': value('odom_source'),
                'zed_config': str(base_share / 'config/zed_flownav.yaml'),
                'serial_port': value('serial_port'),
                'serial_number': value('serial_number'),
                'rviz': 'false',
            }.items()),
        Node(package='nav2_controller', executable='controller_server',
             name='controller_server', parameters=[str(params)], output='screen',
             remappings=[('cmd_vel', '/flownav/cmd_vel_nav')]),
        Node(package='nav2_velocity_smoother', executable='velocity_smoother',
             name='velocity_smoother_flownav', parameters=[str(params)], output='screen',
             remappings=[('cmd_vel', '/flownav/cmd_vel_nav'),
                         ('cmd_vel_smoothed', smoother_output)]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='flownav_lifecycle_manager', output='screen',
             parameters=[{'autostart': True, 'node_names': [
                 'controller_server', 'velocity_smoother_flownav'] +
                 (['collision_monitor'] if hybrid else [])}]),
        Node(package='experiment_cat', executable='flownav_follow_path',
             name='flownav_follow_path', output='screen',
             parameters=[{'image_topic': image_topic, 'lens_frame': lens_frame,
                          'hybrid': hybrid,
                          'meters_per_unit': ParameterValue(
                              LaunchConfiguration('meters_per_unit'), value_type=float)}]),
        ExecuteProcess(
            cmd=[value('python_executable'), str(script)] + inference_args,
            cwd=str(script.parent), additional_env=env,
            output='screen'),
    ]
    if hybrid:
        actions.insert(3, Node(package='nav2_collision_monitor', executable='collision_monitor',
                               name='collision_monitor', parameters=[str(params)], output='screen'))
    return actions


def generate_launch_description():
    workspace = Path('/home/uedalab/ros2_ws')
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='normal', choices=['normal', 'hybrid']),
        DeclareLaunchArgument('task', default_value='navigate', choices=['navigate', 'explore']),
        DeclareLaunchArgument('lens', default_value='left', choices=['left', 'right']),
        DeclareLaunchArgument('odom_source', default_value='vio', choices=['vio', 'wheel']),
        DeclareLaunchArgument('flownav_repo', default_value=str(workspace / 'src/flownav')),
        DeclareLaunchArgument('model_ckpt', default_value=str(workspace / 'models/flownav/flownav_weights.pth')),
        DeclareLaunchArgument('python_executable', default_value=str(workspace / 'src/flownav/.venv/bin/python')),
        DeclareLaunchArgument('topomap', default_value=str(workspace / 'data/flownav/topomaps/default')),
        DeclareLaunchArgument('goal_node', default_value='-1'),
        DeclareLaunchArgument('goal_image', default_value=''),
        DeclareLaunchArgument('goal_detect_threshold', default_value='5.0'),
        DeclareLaunchArgument('goal_threshold', default_value='1.0'),
        DeclareLaunchArgument('log_dir', default_value=str(workspace / 'data/flownav/logs')),
        DeclareLaunchArgument('meters_per_unit', default_value='0.10'),
        DeclareLaunchArgument('serial_port', default_value='/dev/rplidar'),
        DeclareLaunchArgument('serial_number', default_value='10028118'),
        OpaqueFunction(function=start),
    ])
