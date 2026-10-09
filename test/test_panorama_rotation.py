"""Exercise motion state transitions without connecting to a robot or ROS graph."""
import importlib.util
from importlib.machinery import SourceFileLoader
import math
from pathlib import Path
import time
from types import MethodType, SimpleNamespace as NS

import pytest
from rclpy.task import Future
from sensor_msgs.msg import Joy
from std_srvs.srv import Trigger

loader = SourceFileLoader('panorama_rotate_impl', str(Path(__file__).parents[1]/'scripts/panorama_rotate'))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
Controller, TurnPlan = module.PanoramaRotate, module.TurnPlan


def subject():
    obj = NS()
    for name in ('transition', 'receive_joy', 'zero', 'request_brake', 'request_cancel',
                 'abort', 'call', 'poll_service', 'advance', 'tick'):
        setattr(obj, name, MethodType(getattr(Controller, name), obj))
    # Tests set this marker when exercising an active scan; Node.active is a property.
    obj.active = True
    obj.state, obj.detail, obj.phase_since = 'turning', '', time.monotonic()
    obj.scan_since = obj.last_tick = obj.phase_since
    obj.steps, obj.speed, obj.min_speed, obj.accel, obj.tolerance = 12, .45, 0., .8, math.radians(2.)
    obj.settle_time, obj.start_timeout = .5, 25.
    obj.operation_timeout, obj.scan_timeout, obj.turn_timeout = 30., 240., 20.
    obj.a, obj.b, obj.x, obj.y = 0, 1, 2, 3
    obj.a_released, obj.buttons, obj.joy_stamp = True, [0]*4, 0.
    obj.fresh = dict.fromkeys(('joy', 'base', 'odom', 'capture'), time.monotonic())
    obj.base_status = '2: NAVIGATION: Nav2 command enabled'
    obj.capture_status = dict(ready=True, state='recording', frames=1, path='session')
    obj.session = 'session'
    obj.pose = (0., 1., 0., 0.)
    obj.plan = TurnPlan(*obj.pose, 12)
    obj.step, obj.frames, obj.last_speed = 1, 1, 0.
    obj.linear_speed = obj.measured_speed = 0.
    obj.settled_since = obj.pending = None
    obj.commands, obj.calls = [], []
    obj.output = NS(publish=lambda msg: obj.commands.append(msg))
    obj.status = NS(publish=lambda msg: None)
    def client(name):
        def call(request):
            obj.calls.append(name)
            return Future()
        return NS(service_is_ready=lambda: True, call_async=call)
    obj.scan_clients = {name: client(name) for name in ('start', 'capture', 'finish', 'cancel')}
    obj.brake = client('brake')
    obj.get_logger = lambda: NS(info=lambda text: None)
    obj.get_clock = lambda: NS(now=lambda: NS(nanoseconds=100_000_000_000))
    obj.count_publishers = lambda topic: 1
    return obj


def test_unwrap_one_turn_crossing_pi_and_reject_reset():
    plan = TurnPlan(math.radians(170), 1., 0., 0., 24)
    for i in range(1, 361):
        yaw = math.atan2(math.sin(math.radians(170+i)), math.cos(math.radians(170+i)))
        plan.observe(yaw, 1+i*.05, 0., 0., .3)
    assert plan.progress == pytest.approx(2*math.pi)
    assert abs(plan.error(24)) < 1e-10
    with pytest.raises(ValueError, match='jump'):
        plan.observe(0., 19.05, 0., 0., .3)


@pytest.mark.parametrize('cause', ['joy', 'odom', 'capture', 'base', 'duplicate'])
def test_input_loss_and_conflicting_commands_stop_rotation(cause):
    obj = subject()
    if cause == 'duplicate':
        obj.count_publishers = lambda topic: 2
    else:
        obj.fresh[cause] = -math.inf
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'error'
    assert {'brake', 'cancel'} <= set(obj.calls)
    assert all(msg.angular.z == 0 and msg.linear.x == 0 for msg in obj.commands)


def test_angle_control_only_turns_then_waits_for_stationary_capture():
    obj = subject()
    obj.advance(time.monotonic(), .05)
    assert 0 < obj.commands[-1].angular.z <= .8*.05
    assert obj.commands[-1].linear.x == 0
    obj.plan.progress = 2*math.pi/12
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'settling' and obj.commands[-1].angular.z == 0
    obj.advance(time.monotonic(), .05)
    assert obj.pending is None
    obj.settled_since -= .6
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'capture_wait' and obj.calls[-1] == 'capture'


def test_no_rotation_until_capture_ack_and_new_frame_count():
    obj = subject()
    obj.state = 'frame_wait'
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'frame_wait' and not obj.commands
    obj.capture_status['frames'] = 2
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'turning' and obj.step == 2


def test_twelve_captures_then_return_to_start_without_duplicate_frame():
    obj = subject()
    obj.step, obj.frames, obj.state = 11, 11, 'frame_wait'
    obj.capture_status['frames'] = 12
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'turning' and obj.step == 12
    obj.plan.progress = 2*math.pi
    obj.state = 'settling'
    obj.settled_since = time.monotonic()-.6
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'finish_wait'
    assert obj.calls == ['brake', 'finish']
    obj.capture_status['state'] = 'complete'
    obj.advance(time.monotonic(), .05)
    assert obj.state == 'done'
    assert all(cmd.angular.z == 0 for cmd in obj.commands)


def test_b_wins_over_simultaneous_a_and_repeated_a_does_not_restart():
    obj = subject()
    msg = Joy()
    msg.header.stamp.sec = 100
    msg.buttons = [1, 1, 0, 0]
    obj.receive_joy(msg)
    assert obj.state == 'error'
    assert obj.calls == ['brake', 'cancel']
    obj = subject()
    msg.buttons = [1, 0, 0, 0]
    obj.receive_joy(msg)
    assert obj.state == 'turning' and not obj.calls


def test_service_failure_does_not_enable_motion_and_late_reply_is_cancelled():
    obj = subject()
    obj.call('capture', 'capture_wait')
    obj.pending[2].set_result(Trigger.Response(success=False, message='No depth'))
    obj.poll_service()
    assert obj.state == 'error'
    obj = subject()
    obj.call('start', 'start_wait')
    obj.abort('B pressed')
    obj.pending[2].set_result(Trigger.Response(success=True, message='late session'))
    obj.poll_service()
    assert obj.state == 'error' and obj.calls[-1] == 'cancel'


def test_excessive_base_translation_is_rejected():
    plan = TurnPlan(0., 1., 0., 0., 24)
    with pytest.raises(ValueError, match='moved'):
        plan.observe(.01, 1.05, .31, 0., .3)
