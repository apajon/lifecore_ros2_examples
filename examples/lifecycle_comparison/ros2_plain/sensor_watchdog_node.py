"""Plain ROS 2 implementation of the sensor watchdog comparison example.

Single idea: resources are created immediately in ``__init__``. This is simple
and good for prototypes, but the subscriber, timer, and publisher all become
active immediately because there is no configure, activate, or deactivate
transition to control startup behavior.

Drive it::

    uv run python examples/lifecycle_comparison/ros2_plain/sensor_watchdog_node.py
    ros2 topic echo /sensor/status
    ros2 topic pub --once /sensor/value std_msgs/msg/Float64 "{data: 42.0}"

Expected output::

    [startup] Plain sensor watchdog started immediately.
    [status]  WAITING_FOR_FIRST_SAMPLE
    [status]  OK value=42.000
    [status]  STALE age=1.001s
"""

from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64, String


class SensorWatchdogNode(Node):
    """Plain ROS 2 sensor watchdog that starts work as soon as the node starts."""

    def __init__(self) -> None:
        super().__init__("sensor_watchdog_plain")

        self.declare_parameter("stale_timeout_sec", 1.0)
        self.declare_parameter("watchdog_period_sec", 0.2)

        self._stale_timeout_sec = self.get_parameter("stale_timeout_sec").get_parameter_value().double_value
        watchdog_period_sec = self.get_parameter("watchdog_period_sec").get_parameter_value().double_value

        self._last_value: float | None = None
        self._last_stamp: float | None = None
        self._last_logged_status_kind: str | None = None

        self._status_pub = self.create_publisher(String, "/sensor/status", 10)
        self._sensor_sub = self.create_subscription(Float64, "/sensor/value", self._on_sensor_value, 10)
        self._watchdog_timer = self.create_timer(watchdog_period_sec, self._on_watchdog_tick)

        self.get_logger().info("Plain sensor watchdog started immediately.")

    def _on_sensor_value(self, msg: Float64) -> None:
        self._last_value = msg.data
        self._last_stamp = time.monotonic()

    def _on_watchdog_tick(self) -> None:
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


def main() -> None:
    rclpy.init()
    node = SensorWatchdogNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
