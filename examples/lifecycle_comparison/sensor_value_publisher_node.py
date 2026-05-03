"""Plain ROS 2 sensor value publisher for the lifecycle comparison examples.

Single idea: this node is an external runtime stimulus shared by all watchdog
variants. It publishes deterministic ``Float64`` samples on ``/sensor/value``
without adding shared implementation code to the compared watchdog nodes.

Drive it::

    uv run python examples/lifecycle_comparison/sensor_value_publisher_node.py
    ros2 topic echo /sensor/value
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64


class SensorValuePublisherNode(Node):
    """Minimal plain ROS 2 node that publishes sensor values periodically."""

    def __init__(self) -> None:
        super().__init__("sensor_value_publisher_plain")

        self.declare_parameter("publish_period_sec", 0.2)
        self.declare_parameter("initial_value", 0.0)
        self.declare_parameter("step", 1.0)

        publish_period_sec = self.get_parameter("publish_period_sec").get_parameter_value().double_value
        self._next_value = self.get_parameter("initial_value").get_parameter_value().double_value
        self._step = self.get_parameter("step").get_parameter_value().double_value

        self._publisher = self.create_publisher(Float64, "/sensor/value", 10)
        self._timer = self.create_timer(publish_period_sec, self._publish_value)

        self.get_logger().info(
            f"Sensor value publisher started on /sensor/value with period={publish_period_sec:.3f}s"
        )

    def _publish_value(self) -> None:
        msg = Float64()
        msg.data = self._next_value
        self._publisher.publish(msg)
        self._next_value += self._step


def main() -> None:
    rclpy.init()
    node = SensorValuePublisherNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
