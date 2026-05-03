# Lifecycle Comparison: Sensor Watchdog

This example compares the same `sensor_watchdog` node in three styles:

- plain ROS 2
- classic ROS 2 lifecycle
- `lifecore_ros2` component-oriented lifecycle

The node receives sensor values on `/sensor/value` with `std_msgs/msg/Float64`,
publishes watchdog status on `/sensor/status` with `std_msgs/msg/String`, and
checks periodically whether the last sample is fresh.

## Sensor Publisher

Run the shared plain ROS 2 sensor publisher in one terminal:

```bash
uv run python examples/lifecycle_comparison/sensor_value_publisher_node.py
```

Watch sensor samples in another terminal:

```bash
ros2 topic echo /sensor/value
```

## Plain ROS 2

Run the plain ROS 2 watchdog implementation:

```bash
uv run python examples/lifecycle_comparison/ros2_plain/sensor_watchdog_node.py
```

Watch status output in another terminal:

```bash
ros2 topic echo /sensor/status
```

Publish a sample:

```bash
ros2 topic pub --once /sensor/value std_msgs/msg/Float64 "{data: 42.0}"
```

You can use this one-shot command instead of the shared sensor publisher when
you want to force a single sample manually.

Expected behavior:

- the node starts receiving, checking, and publishing immediately;
- status starts as `WAITING_FOR_FIRST_SAMPLE`;
- after a sample, status becomes `OK value=<value>`;
- after the stale timeout, status becomes `STALE age=<seconds>s`.

This demonstrates the strength and limit of a plain ROS 2 node: it is very
simple and perfect for a prototype, but the subscriber, timer, and publisher are
active immediately. There is no configure, activate, or deactivate transition,
so startup behavior is not controlled by the ROS 2 lifecycle.

## Classic ROS 2 Lifecycle

Run the classic lifecycle watchdog implementation:

```bash
uv run python examples/lifecycle_comparison/ros2_lifecycle_classic/sensor_watchdog_lifecycle_node.py
```

Drive lifecycle transitions from another terminal:

```bash
ros2 lifecycle set /sensor_watchdog_classic configure
ros2 lifecycle set /sensor_watchdog_classic activate
ros2 lifecycle set /sensor_watchdog_classic deactivate
ros2 lifecycle set /sensor_watchdog_classic cleanup
```

Expected behavior:

- configure creates the subscriber, lifecycle publisher, and timer;
- the lifecycle publisher uses native lifecycle enable/disable behavior;
- while inactive, the watchdog timer is canceled and sensor samples are ignored;
- activate enables sensor handling, watchdog checks, and status publication;
- deactivate cancels the timer and gates behavior again while keeping resources configured;
- cleanup releases the subscriber, publisher, and timer.

This demonstrates both sides of classic ROS 2 lifecycle plumbing: lifecycle
publishers are native, but subscriptions and timers are not automatically made
lifecycle-aware, so the node still needs manual activation flags and guarded
callbacks.

## lifecore_ros2

Run the Lifecore watchdog implementation:

```bash
uv run python examples/lifecycle_comparison/lifecore_ros2/sensor_watchdog_lifecore_node.py
```

Drive lifecycle transitions from another terminal:

```bash
ros2 lifecycle set /sensor_watchdog_lifecore configure
ros2 lifecycle set /sensor_watchdog_lifecore activate
ros2 lifecycle set /sensor_watchdog_lifecore deactivate
ros2 lifecycle set /sensor_watchdog_lifecore cleanup
```

Expected behavior:

- the node describes the architecture by wiring explicit component dependencies;
- `SensorStateComponent` owns the latest-sample state and lifecycle reset;
- `SensorSubscriberComponent` owns the `/sensor/value` subscription and updates the state;
- `WatchdogStatusPublisher` owns status publication;
- `WatchdogTimer` owns periodic freshness checks;
- Lifecore gates subscriber callbacks, timer ticks, and publisher calls through component activation;
- the watchdog timer starts on activate and stops on deactivate through its component lifecycle hooks;
- the application node does not carry lifecycle flags or resource cleanup plumbing.
