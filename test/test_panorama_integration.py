"""Synthetic RGB-D + TF + joystick test with the real command gate; no hardware.

Run in an isolated ROS domain. No launch file, camera driver or motor driver runs.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.spatial.transform import Rotation
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from ament_index_python.packages import get_package_prefix
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, CameraInfo, Joy
from std_msgs.msg import UInt8
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster

from cat_panorama.capture_node import PanoramaCapture


def load_script(name, path):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


Rotate = load_script('scan_controller', Path(__file__).parents[1]/'scripts/panorama_rotate').PanoramaRotate
Safety = load_script('scan_safety', Path(get_package_prefix('cat_bringup'))/'lib/cat_bringup/base_safety').BaseSafety


class SyntheticRobot(Node):
    def __init__(self):
        super().__init__('synthetic_panorama_robot')
        self.yaw, self.command, self.last = 0., 0., time.monotonic()
        self.buttons = [0]*4
        self.images_enabled = True
        self.motion_count = 0
        self.bridge = CvBridge()
        self.odom = self.create_publisher(Odometry, '/odom', 10)
        self.joy = self.create_publisher(Joy, '/joy', qos_profile_sensor_data)
        self.motor = self.create_publisher(UInt8, '/base/state', 1)
        self.rgb = self.create_publisher(Image, '/zed/zed_node/rgb/color/rect/image', qos_profile_sensor_data)
        self.depth = self.create_publisher(Image, '/zed/zed_node/depth/depth_registered', qos_profile_sensor_data)
        self.info = self.create_publisher(CameraInfo, '/zed/zed_node/rgb/color/rect/camera_info', qos_profile_sensor_data)
        self.create_subscription(Twist, '/cmd_vel_safe', self.receive_command, 1)
        self.tf = TransformBroadcaster(self)
        self.static_tf = StaticTransformBroadcaster(self)
        self.optical = np.array([[0., 0., 1.], [-1., 0., 0.], [0., -1., 0.]])
        self.mount = np.array([-.27, .03, .54675])
        transform = TransformStamped()
        transform.header.frame_id = 'base_link'
        transform.child_frame_id = 'camera_optical'
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.transform.translation.x, transform.transform.translation.y, transform.transform.translation.z = self.mount.tolist()
        q = Rotation.from_matrix(self.optical).as_quat()
        transform.transform.rotation.x, transform.transform.rotation.y, transform.transform.rotation.z, transform.transform.rotation.w = q.tolist()
        self.static_tf.sendTransform(transform)
        self.create_timer(.025, self.tick)

    def receive_command(self, msg):
        assert msg.linear.x == 0.
        assert abs(msg.angular.z) <= .5+1e-6
        self.command = msg.angular.z
        if self.command:
            self.motion_count += 1

    def tick(self):
        now = time.monotonic()
        # Accelerated synthetic plant stays below the controller's jump threshold.
        speed = self.command*3
        self.yaw += speed*(now-self.last)
        self.last = now
        stamp = self.get_clock().now().to_msg()
        joy = Joy()
        joy.header.stamp, joy.buttons = stamp, self.buttons
        self.joy.publish(joy)
        self.motor.publish(UInt8(data=3 if abs(speed) < .01 else 1))
        odom = Odometry()
        odom.header.stamp, odom.header.frame_id, odom.child_frame_id = stamp, 'odom', 'base_link'
        odom.pose.pose.orientation.z, odom.pose.pose.orientation.w = math.sin(self.yaw/2), math.cos(self.yaw/2)
        odom.twist.twist.angular.z = speed
        self.odom.publish(odom)
        transform = TransformStamped()
        transform.header, transform.child_frame_id = odom.header, 'base_link'
        transform.transform.rotation = odom.pose.pose.orientation
        self.tf.sendTransform(transform)
        if not self.images_enabled:
            return
        info = CameraInfo()
        info.header.stamp, info.header.frame_id = stamp, 'camera_optical'
        info.width, info.height = 96, 64
        info.p = [60., 0., 47.5, 0., 0., 60., 31.5, 0., 0., 0., 1., 0.]
        self.info.publish(info)
        yy, xx = np.indices((64, 96))
        rays = np.stack(((xx-47.5)/60, (yy-31.5)/60, np.ones_like(xx)), axis=-1)
        rotation = Rotation.from_euler('z', self.yaw).as_matrix()
        world_rays = rays @ (rotation @ self.optical).T
        center = rotation @ self.mount - np.array([0., 0., .54675])
        a = np.sum(world_rays**2, axis=-1)
        b = 2*np.sum(world_rays*center, axis=-1)
        c = np.sum(center**2)-9.
        z = (-b+np.sqrt(b*b-4*a*c))/(2*a)
        points = world_rays*z[..., None]+center
        colors = np.clip((points/3+1)*127, 0, 255).astype(np.uint8)
        rgb = self.bridge.cv2_to_imgmsg(colors, 'bgr8')
        depth = self.bridge.cv2_to_imgmsg(z.astype(np.float32), '32FC1')
        rgb.header = depth.header = info.header
        self.rgb.publish(rgb)
        self.depth.publish(depth)


def test_a_full_scan_save_then_b_cancel_and_sensor_loss(tmp_path, monkeypatch):
    # Separate from normal hardware domain 0; localhost only.
    monkeypatch.setenv('ROS_DOMAIN_ID', '187')
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path/'ros_logs'))
    rclpy.init()
    capture = PanoramaCapture(parameter_overrides=[
        Parameter('output_dir', value=str(tmp_path/'panoramas')),
        Parameter('width', value=256), Parameter('height', value=128),
        Parameter('save_frames', value=True)])
    rotate = Rotate(parameter_overrides=[
        Parameter('steps', value=12), Parameter('angular_speed', value=.5),
        Parameter('angular_acceleration', value=3.), Parameter('settle_time', value=.1)])
    safety, robot = Safety(), SyntheticRobot()
    executor = SingleThreadedExecutor()
    nodes = (capture, rotate, safety, robot)
    for node in nodes:
        executor.add_node(node)

    def until(condition, timeout=10.):
        deadline = time.monotonic()+timeout
        while not condition() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=.01)
        assert condition(), (rotate.state, rotate.detail, capture.state, capture.wait_reason,
                             safety.mode, safety.reason)

    def pump(seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=.01)

    def press_a():
        robot.buttons = [1, 0, 0, 0]
        pump(.15)
        robot.buttons = [0]*4

    try:
        until(lambda: capture.ready() and rotate.a_released)
        assert robot.motion_count == 0 and rotate.state == 'idle'
        press_a()
        until(lambda: rotate.state in ('done', 'error'), 90.)
        assert rotate.state == 'done', rotate.detail
        assert robot.motion_count > 0 and rotate.frames == 12
        folder = Path(rotate.session)
        metadata = json.loads((folder/'metadata.json').read_text())
        depth = np.load(folder/'depth_m.npy')
        assert metadata['state'] == 'complete' and metadata['frame_count'] == 12
        # The world is a 3 m sphere; verify metric reprojection compensates mounting offset.
        np.testing.assert_allclose(depth[np.isfinite(depth)], 3., atol=.02)
        assert np.isfinite(depth).sum() > depth.size*.2
        assert abs(rotate.plan.progress-2*math.pi) < math.radians(2)
        until(lambda: safety.mode == 0 and robot.command == 0)
        # A second scan must get a new directory; B cancels without final outputs.
        press_a()
        until(lambda: rotate.state == 'turning')
        assert rotate.session != str(folder)
        robot.buttons = [0, 1, 0, 0]
        until(lambda: rotate.state == 'error' and safety.mode == 0 and robot.command == 0)
        until(lambda: capture.state == 'cancelled')
        assert not (Path(rotate.session)/'rgb.png').exists()
        robot.buttons = [0]*4
        pump(.15)
        press_a()
        until(lambda: rotate.state == 'turning')
        robot.images_enabled = False
        until(lambda: rotate.state == 'error' and safety.mode == 0 and robot.command == 0)
        assert 'stale' in rotate.detail
    finally:
        capture.close()
        executor.shutdown()
        for node in nodes:
            node.destroy_node()
        rclpy.shutdown()
