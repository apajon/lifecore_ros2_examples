"""Runtime behavior tests for the lifecycle_comparison examples.

Exercises status publication, activation gating, deactivation gating, and cleanup
behavior for each comparison variant.  Timer periods are never awaited: timer
callbacks are invoked directly to keep tests deterministic.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import TransitionCallbackReturn
from rclpy.node import Node
from std_msgs.msg import Float64, String

from examples.lifecycle_comparison.lifecore_ros2.sensor_watchdog_lifecore_node import (
    SensorStateComponent,
    WatchdogTimer,
)
from examples.lifecycle_comparison.lifecore_ros2.sensor_watchdog_lifecore_node import (
    SensorWatchdogNode as LifecoreWatchdogNode,
)
from examples.lifecycle_comparison.ros2_lifecycle_classic.sensor_watchdog_lifecycle_node import (
    SensorWatchdogLifecycleNode,
)
from examples.lifecycle_comparison.ros2_plain.sensor_watchdog_node import (
    SensorWatchdogNode as PlainWatchdogNode,
)
from examples.lifecycle_comparison.sensor_value_publisher_node import SensorValuePublisherNode

# ---------------------------------------------------------------------------
# Module-scoped rclpy context
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _rclpy_context() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Initialize rclpy once for this module; skip shutdown if already initialized."""
    already_ok = rclpy.ok()  # pyright: ignore[reportPrivateImportUsage]
    if not already_ok:
        rclpy.init()
    yield
    if not already_ok:
        rclpy.shutdown()


# ---------------------------------------------------------------------------
# Spin helpers
# ---------------------------------------------------------------------------


def _spin_until(
    condition: Callable[[], bool],
    executor: SingleThreadedExecutor,
    *,
    max_iters: int = 200,
    timeout_sec: float = 0.05,
) -> bool:
    """Spin executor.spin_once until *condition* returns True or max_iters is exhausted."""
    for _ in range(max_iters):
        executor.spin_once(timeout_sec=timeout_sec)
        if condition():
            return True
    return False


def _spin_for(executor: SingleThreadedExecutor, iters: int) -> None:
    """Spin executor.spin_once exactly *iters* times with a zero-wait timeout."""
    for _ in range(iters):
        executor.spin_once(timeout_sec=0.0)


# ---------------------------------------------------------------------------
# Probe nodes
# ---------------------------------------------------------------------------


class _Float64Probe(Node):
    """Minimal subscriber probe for /sensor/value."""

    def __init__(self) -> None:
        super().__init__(f"float64_probe_{uuid.uuid4().hex}")
        self.received: list[float] = []
        self.create_subscription(Float64, "/sensor/value", self._cb, 10)

    def _cb(self, msg: Float64) -> None:
        self.received.append(msg.data)


class _StatusProbe(Node):
    """Minimal subscriber probe for /sensor/status."""

    def __init__(self) -> None:
        super().__init__(f"status_probe_{uuid.uuid4().hex}")
        self.received: list[str] = []
        self.create_subscription(String, "/sensor/status", self._cb, 10)

    def _cb(self, msg: String) -> None:
        self.received.append(msg.data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sensor_value_publisher_emits_float64_samples() -> None:
    """SensorValuePublisherNode publishes Float64 values starting at 0.0 with step 1.0."""
    node = SensorValuePublisherNode()
    probe = _Float64Probe()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(probe)

    try:
        cast(Any, node)._timer.cancel()
        cast(Any, node)._publish_value()
        cast(Any, node)._publish_value()

        ok = _spin_until(lambda: len(probe.received) >= 2, executor)
        assert ok, "Did not receive two Float64 samples in time"
        assert probe.received[0] == 0.0
        assert probe.received[1] == 1.0
    finally:
        node.destroy_node()
        probe.destroy_node()
        executor.shutdown()


def test_plain_watchdog_publishes_waiting_ok_and_stale_statuses() -> None:
    """Plain watchdog emits WAITING_FOR_FIRST_SAMPLE, OK, and STALE statuses on /sensor/status."""
    node = PlainWatchdogNode()
    probe = _StatusProbe()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(probe)

    try:
        cast(Any, node)._watchdog_timer.cancel()

        # WAITING_FOR_FIRST_SAMPLE: no sensor sample received yet
        cast(Any, node)._on_watchdog_tick()
        assert _spin_until(lambda: len(probe.received) >= 1, executor), "WAITING_FOR_FIRST_SAMPLE not received"
        assert probe.received[0] == "WAITING_FOR_FIRST_SAMPLE"

        # OK value=42.000: supply a sensor sample then tick
        sensor_msg = Float64()
        sensor_msg.data = 42.0
        cast(Any, node)._on_sensor_value(sensor_msg)
        cast(Any, node)._on_watchdog_tick()
        assert _spin_until(lambda: len(probe.received) >= 2, executor), "OK status not received"
        assert probe.received[1] == "OK value=42.000"

        # STALE: back-date the stamp so age > stale_timeout_sec
        cast(Any, node)._last_stamp = time.monotonic() - 10.0
        cast(Any, node)._on_watchdog_tick()
        assert _spin_until(lambda: len(probe.received) >= 3, executor), "STALE status not received"
        assert cast(Any, probe.received[2]).startswith("STALE")
    finally:
        node.destroy_node()
        probe.destroy_node()
        executor.shutdown()


def test_classic_lifecycle_gates_runtime_behavior_and_releases_resources() -> None:
    """Classic lifecycle treats inactive runtime misuse as gated no-op behavior."""
    node = SensorWatchdogLifecycleNode()
    probe = _StatusProbe()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(probe)

    try:
        result = node.trigger_configure()
        assert result == TransitionCallbackReturn.SUCCESS

        # Before activate: sensor callback is gated (_active=False)
        sensor_msg = Float64()
        sensor_msg.data = 42.0
        cast(Any, node)._on_sensor_value(sensor_msg)
        assert cast(Any, node)._last_value is None

        # Before activate: watchdog tick must not emit any status
        cast(Any, node)._on_watchdog_tick()
        _spin_for(executor, 20)
        assert len(probe.received) == 0

        # Activate
        result = node.trigger_activate()
        assert result == TransitionCallbackReturn.SUCCESS

        # After activate: tick emits WAITING_FOR_FIRST_SAMPLE (sample was dropped before activate)
        cast(Any, node)._on_watchdog_tick()
        assert _spin_until(lambda: len(probe.received) >= 1, executor), "Status not received after activate"
        assert probe.received[0] == "WAITING_FOR_FIRST_SAMPLE"

        # Deactivate: subsequent callbacks must not change state or publish
        result = node.trigger_deactivate()
        assert result == TransitionCallbackReturn.SUCCESS
        before_count = len(probe.received)
        cast(Any, node)._on_sensor_value(sensor_msg)
        cast(Any, node)._on_watchdog_tick()
        _spin_for(executor, 20)
        assert len(probe.received) == before_count
        assert cast(Any, node)._last_value is None

        # Cleanup: ROS resources released, watchdog state reset
        result = node.trigger_cleanup()
        assert result == TransitionCallbackReturn.SUCCESS
        assert cast(Any, node)._status_pub is None
        assert cast(Any, node)._sensor_sub is None
        assert cast(Any, node)._watchdog_timer is None
        assert cast(Any, node)._active is False
        assert cast(Any, node)._last_value is None
        assert cast(Any, node)._last_stamp is None
    finally:
        node.destroy_node()
        probe.destroy_node()
        executor.shutdown()


def test_lifecore_gates_subscriber_timer_publication_and_cleans_up() -> None:
    """lifecore_ros2 treats inactive runtime misuse as gated no-op behavior."""
    node = LifecoreWatchdogNode()
    probe = _StatusProbe()
    sensor_pub_node: Node = Node(f"sensor_pub_{uuid.uuid4().hex}")
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(probe)
    executor.add_node(sensor_pub_node)

    try:
        result = node.trigger_configure()
        assert result == TransitionCallbackReturn.SUCCESS

        sensor_state = cast(SensorStateComponent, node.get_component("sensor_state"))
        watchdog_timer = cast(WatchdogTimer, node.get_component("watchdog_timer"))

        # Publish a sensor sample before activate: subscriber component must gate it
        sensor_pub = sensor_pub_node.create_publisher(Float64, "/sensor/value", 10)
        sensor_msg = Float64()
        sensor_msg.data = 99.0
        sensor_pub.publish(sensor_msg)
        _spin_for(executor, 30)
        assert sensor_state.last_value is None  # gated: component was not active

        # Timer wrapper before activate: silently no-ops (when_not_active=None)
        cast(Any, watchdog_timer)._on_timer_wrapper()
        _spin_for(executor, 20)
        assert len(probe.received) == 0

        # Activate
        result = node.trigger_activate()
        assert result == TransitionCallbackReturn.SUCCESS
        assert watchdog_timer.is_running

        # Publish a sample and spin until SensorStateComponent records it
        sensor_msg.data = 42.0
        sensor_pub.publish(sensor_msg)
        assert _spin_until(
            lambda: sensor_state.last_value == 42.0, executor
        ), "SensorStateComponent did not receive sample after activate"

        # Tick and verify OK status published to the probe
        cast(Any, watchdog_timer)._on_timer_wrapper()
        assert _spin_until(lambda: len(probe.received) >= 1, executor), "OK status not received after activate"
        assert probe.received[0] == "OK value=42.000"

        # Deactivate: timer stopped, no new state updates or publications
        result = node.trigger_deactivate()
        assert result == TransitionCallbackReturn.SUCCESS
        assert not watchdog_timer.is_running
        before_count = len(probe.received)
        sensor_msg.data = 77.0
        sensor_pub.publish(sensor_msg)
        _spin_for(executor, 30)
        assert sensor_state.last_value == 42.0  # gated: sample dropped
        cast(Any, watchdog_timer)._on_timer_wrapper()
        _spin_for(executor, 20)
        assert len(probe.received) == before_count

        # Cleanup: component resources released and state reset
        result = node.trigger_cleanup()
        assert result == TransitionCallbackReturn.SUCCESS
        assert cast(Any, node.get_component("sensor_subscriber"))._subscription is None
        assert cast(Any, node.get_component("status_publisher"))._publisher is None
        assert cast(Any, watchdog_timer)._timer is None
        assert sensor_state.last_value is None
        assert sensor_state.last_stamp is None
    finally:
        node.destroy_node()
        probe.destroy_node()
        sensor_pub_node.destroy_node()
        executor.shutdown()
