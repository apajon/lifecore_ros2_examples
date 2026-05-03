"""lifecore_ros2 implementation of the sensor watchdog comparison example.

Single idea: the node describes the architecture and each component owns one
responsibility. Component dependencies are explicit in the node wiring, and
Lifecore propagates lifecycle transitions to the components so subscriber
callbacks, timer ticks, and status publication are gated without an activation
flag in the application node.

Drive it::

    uv run python examples/lifecycle_comparison/lifecore_ros2/sensor_watchdog_lifecore_node.py
    ros2 lifecycle set /sensor_watchdog_lifecore configure
    ros2 lifecycle set /sensor_watchdog_lifecore activate
    ros2 lifecycle set /sensor_watchdog_lifecore deactivate
    ros2 lifecycle set /sensor_watchdog_lifecore cleanup
"""

from __future__ import annotations

import time

import rclpy
from lifecore_ros2 import (
    LifecycleComponent,
    LifecycleComponentNode,
    LifecyclePublisherComponent,
    LifecycleSubscriberComponent,
    LifecycleTimerComponent,
)
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import TransitionCallbackReturn
from rclpy.lifecycle.node import LifecycleState
from std_msgs.msg import Float64, String


class SensorStateComponent(LifecycleComponent):
    """Owns the latest sensor sample as lifecycle-managed state."""

    def __init__(self) -> None:
        super().__init__(name="sensor_state")
        self._last_value: float | None = None
        self._last_stamp: float | None = None

    @property
    def last_value(self) -> float | None:
        return self._last_value

    @property
    def last_stamp(self) -> float | None:
        return self._last_stamp

    def update(self, value: float) -> None:
        self._last_value = value
        self._last_stamp = time.monotonic()

    def reset(self) -> None:
        self._last_value = None
        self._last_stamp = None

    def _on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.reset()
        return TransitionCallbackReturn.SUCCESS

    def _on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.reset()
        return TransitionCallbackReturn.SUCCESS

    def _on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.reset()
        return TransitionCallbackReturn.SUCCESS


class SensorSubscriberComponent(LifecycleSubscriberComponent[Float64]):
    """Receives sensor values while active and updates lifecycle-managed state."""

    def __init__(self, sensor_state: SensorStateComponent) -> None:
        super().__init__(
            name="sensor_subscriber",
            topic_name="/sensor/value",
            msg_type=Float64,
            qos_profile=10,
        )
        self._sensor_state = sensor_state

    def on_message(self, msg: Float64) -> None:
        self._sensor_state.update(msg.data)


class WatchdogStatusPublisher(LifecyclePublisherComponent[String]):
    """Publishes watchdog status while active."""

    def __init__(self) -> None:
        super().__init__(
            name="status_publisher",
            topic_name="/sensor/status",
            msg_type=String,
            qos_profile=10,
        )

    def publish_status(self, status_text: str) -> None:
        status = String()
        status.data = status_text
        self.publish(status)


class WatchdogTimer(LifecycleTimerComponent):
    """Checks sample freshness and publishes status while active."""

    def __init__(
        self,
        sensor_state: SensorStateComponent,
        status_publisher: WatchdogStatusPublisher,
        *,
        stale_timeout_sec: float,
        watchdog_period_sec: float,
    ) -> None:
        super().__init__(name="watchdog_timer", period=watchdog_period_sec, autostart=False)
        self._sensor_state = sensor_state
        self._status_publisher = status_publisher
        self._stale_timeout_sec = stale_timeout_sec
        self._last_logged_status_kind: str | None = None

    def _on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.start()
        self.node.get_logger().info(f"[{self.name}] watchdog timer started")
        return TransitionCallbackReturn.SUCCESS

    def _on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.stop()
        self.node.get_logger().info(f"[{self.name}] watchdog timer stopped")
        return TransitionCallbackReturn.SUCCESS

    def _on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._last_logged_status_kind = None
        return TransitionCallbackReturn.SUCCESS

    def _on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._last_logged_status_kind = None
        return TransitionCallbackReturn.SUCCESS

    def _on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._last_logged_status_kind = None
        return TransitionCallbackReturn.SUCCESS

    def on_tick(self) -> None:
        status_text, status_kind = self._build_status()
        self._status_publisher.publish_status(status_text)

        if status_kind != self._last_logged_status_kind:
            self.node.get_logger().info(f"Watchdog status: {status_text}")
            self._last_logged_status_kind = status_kind

    def _build_status(self) -> tuple[str, str]:
        last_stamp = self._sensor_state.last_stamp
        last_value = self._sensor_state.last_value
        if last_stamp is None or last_value is None:
            return "WAITING_FOR_FIRST_SAMPLE", "waiting"

        age = time.monotonic() - last_stamp
        if age > self._stale_timeout_sec:
            return f"STALE age={age:.3f}s", "stale"

        return f"OK value={last_value:.3f}", "ok"


class SensorWatchdogNode(LifecycleComponentNode):
    """Sensor watchdog whose node body only wires component responsibilities."""

    def __init__(self) -> None:
        super().__init__("sensor_watchdog_lifecore")

        self.declare_parameter("stale_timeout_sec", 1.0)
        self.declare_parameter("watchdog_period_sec", 0.2)

        stale_timeout_sec = self.get_parameter("stale_timeout_sec").get_parameter_value().double_value
        watchdog_period_sec = self.get_parameter("watchdog_period_sec").get_parameter_value().double_value

        self._status_publisher = WatchdogStatusPublisher()
        self._sensor_state = SensorStateComponent()
        self._sensor_subscriber = SensorSubscriberComponent(self._sensor_state)
        self._watchdog_timer = WatchdogTimer(
            self._sensor_state,
            self._status_publisher,
            stale_timeout_sec=stale_timeout_sec,
            watchdog_period_sec=watchdog_period_sec,
        )

        self.add_components(self._components_in_dependency_order())

    def _components_in_dependency_order(
        self,
    ) -> tuple[SensorStateComponent, WatchdogStatusPublisher, SensorSubscriberComponent, WatchdogTimer]:
        """Return components in architectural dependency order for registration."""
        return (
            self._sensor_state,
            self._status_publisher,
            self._sensor_subscriber,
            self._watchdog_timer,
        )


def main() -> None:
    rclpy.init(args=["--ros-args", "--log-level", "sensor_watchdog_lifecore:=debug"])

    node = SensorWatchdogNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    try:
        node.get_logger().info("Lifecore watchdog ready - configure and activate to publish status")
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.remove_node(node)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
