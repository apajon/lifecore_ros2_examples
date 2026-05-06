"""Classic ROS 2 lifecycle implementation of the sensor watchdog example.

Single idea: ROS resources are created in ``on_configure`` and retained while
inactive. The lifecycle publisher is native, the timer is canceled while
inactive, and subscriber callbacks are still guarded by hand because ROS 2
subscriptions are not lifecycle-aware.

Drive it::

    uv run python examples/lifecycle_comparison/ros2_lifecycle_classic/sensor_watchdog_lifecycle_node.py
    ros2 lifecycle set /sensor_watchdog_classic configure
    ros2 lifecycle set /sensor_watchdog_classic activate
    ros2 lifecycle set /sensor_watchdog_classic deactivate
    ros2 lifecycle set /sensor_watchdog_classic cleanup
"""

from __future__ import annotations

import time
from typing import cast

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode, LifecyclePublisher, TransitionCallbackReturn
from rclpy.lifecycle.node import LifecycleState
from rclpy.subscription import Subscription
from rclpy.timer import Timer
from std_msgs.msg import Float64, String


class SensorWatchdogLifecycleNode(LifecycleNode):
    """Classic lifecycle watchdog with explicit transition plumbing."""

    def __init__(self) -> None:
        super().__init__("sensor_watchdog_classic")

        self.declare_parameter("stale_timeout_sec", 1.0)
        self.declare_parameter("watchdog_period_sec", 0.2)

        self._stale_timeout_sec: float = 1.0
        self._last_value: float | None = None
        self._last_stamp: float | None = None
        self._last_logged_status_kind: str | None = None
        self._active = False

        self._status_pub: LifecyclePublisher | None = None
        self._sensor_sub: Subscription | None = None
        self._watchdog_timer: Timer | None = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._stale_timeout_sec = self.get_parameter("stale_timeout_sec").get_parameter_value().double_value
        watchdog_period_sec = self.get_parameter("watchdog_period_sec").get_parameter_value().double_value

        self._status_pub = cast(LifecyclePublisher, self.create_lifecycle_publisher(String, "/sensor/status", 10))
        self._sensor_sub = self.create_subscription(Float64, "/sensor/value", self._on_sensor_value, 10)
        self._watchdog_timer = self.create_timer(watchdog_period_sec, self._on_watchdog_tick)
        self._watchdog_timer.cancel()

        self.get_logger().info(
            "Classic lifecycle watchdog configured with "
            f"period={watchdog_period_sec:.3f}s timeout={self._stale_timeout_sec:.3f}s"
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = super().on_activate(state)
        if result != TransitionCallbackReturn.SUCCESS:
            return result

        self._active = True
        if self._watchdog_timer is not None:
            self._watchdog_timer.reset()

        self.get_logger().info("Classic lifecycle watchdog activated.")
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._active = False
        if self._watchdog_timer is not None:
            self._watchdog_timer.cancel()

        result = super().on_deactivate(state)
        if result != TransitionCallbackReturn.SUCCESS:
            return result

        self.get_logger().info("Classic lifecycle watchdog deactivated.")
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        result = super().on_cleanup(state)
        if result != TransitionCallbackReturn.SUCCESS:
            return result

        self._release_resources()
        self._reset_watchdog_state()
        self.get_logger().info("Classic lifecycle watchdog cleaned up.")
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._active = False
        result = super().on_shutdown(state)
        if result != TransitionCallbackReturn.SUCCESS:
            return result

        self._release_resources()
        self.get_logger().info("Classic lifecycle watchdog shut down.")
        return TransitionCallbackReturn.SUCCESS

    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        self._active = False
        self.get_logger().error("Classic lifecycle watchdog entered error handling.")
        return TransitionCallbackReturn.SUCCESS

    def _on_sensor_value(self, msg: Float64) -> None:
        if not self._active:
            return

        self._last_value = msg.data
        self._last_stamp = time.monotonic()

    def _on_watchdog_tick(self) -> None:
        if not self._active or self._status_pub is None:
            return

        status_text, status_kind = self._build_status()

        status = String()
        status.data = status_text
        self._status_pub.publish(status)

        if status_kind != self._last_logged_status_kind:
            self.get_logger().info(f"Watchdog status: {status_text}")
            self._last_logged_status_kind = status_kind

    def _build_status(self) -> tuple[str, str]:
        if self._last_stamp is None or self._last_value is None:
            return "WAITING_FOR_FIRST_SAMPLE", "waiting"

        age = time.monotonic() - self._last_stamp
        if age > self._stale_timeout_sec:
            return f"STALE age={age:.3f}s", "stale"

        return f"OK value={self._last_value:.3f}", "ok"

    def _release_resources(self) -> None:
        if self._watchdog_timer is not None:
            self.destroy_timer(self._watchdog_timer)
            self._watchdog_timer = None

        if self._sensor_sub is not None:
            self.destroy_subscription(self._sensor_sub)
            self._sensor_sub = None

        if self._status_pub is not None:
            self.destroy_publisher(self._status_pub)
            self._status_pub = None

    def _reset_watchdog_state(self) -> None:
        self._active = False
        self._last_value = None
        self._last_stamp = None
        self._last_logged_status_kind = None


def main() -> None:
    rclpy.init(args=["--ros-args", "--log-level", "sensor_watchdog_classic:=debug"])

    node = SensorWatchdogLifecycleNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    try:
        node.get_logger().info("Classic lifecycle watchdog ready - configure and activate to publish status")
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.remove_node(node)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
