# Lifecycle Comparison: Sensor Watchdog

This example compares the same `sensor_watchdog` node in three styles:

- plain ROS 2
- classic ROS 2 lifecycle
- `lifecore_ros2` component-oriented lifecycle

The goal is not to show three ways to write the same node for style points. The goal is to expose where lifecycle behavior lives:

- in the whole node, with plain ROS 2;
- partly in ROS 2 lifecycle primitives and partly in manual guards, with classic lifecycle nodes;
- in explicit lifecycle-aware components, with `lifecore_ros2`.

`lifecore_ros2` does not replace the native ROS 2 lifecycle state machine. It keeps the node lifecycle native and adds a small component ownership layer inside the node.

The node receives sensor values on `/sensor/value` with `std_msgs/msg/Float64`,
publishes watchdog status on `/sensor/status` with `std_msgs/msg/String`, and
checks periodically whether the last sample is fresh.

Keep one observation terminal open while you run any watchdog variant:

```bash
ros2 topic echo /sensor/status
```

If you also want to watch the shared stimulus, open another terminal with:

```bash
ros2 topic echo /sensor/value
```

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

Expected topic and log signals:

- the node starts receiving, checking, and publishing immediately;
- the startup log says `Plain sensor watchdog started immediately.`;
- status starts as `WAITING_FOR_FIRST_SAMPLE`;
- after a sample, status becomes `OK value=<value>`;
- after the stale timeout, status becomes `STALE age=<seconds>s`;
- each status transition is also logged as `Watchdog status: ...`.

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

Expected topic and log signals:

- `configure` logs `Classic lifecycle watchdog configured ...` and creates the subscriber, lifecycle publisher, and timer;
- before `activate`, `/sensor/status` stays silent even if samples arrive;
- the lifecycle publisher uses native lifecycle enable/disable behavior;
- while inactive, the watchdog timer is canceled and sensor samples are ignored;
- `activate` logs `Classic lifecycle watchdog activated.` and allows `WAITING_FOR_FIRST_SAMPLE`, `OK value=<value>`, then `STALE age=<seconds>s` on `/sensor/status` and in `Watchdog status: ...` logs;
- `deactivate` logs `Classic lifecycle watchdog deactivated.` and gates behavior again while keeping resources configured, so `/sensor/status` stops changing while inactive;
- `cleanup` releases the subscriber, publisher, and timer and logs `Classic lifecycle watchdog cleaned up.`.

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

Expected topic and log signals:

- the node describes the architecture by wiring explicit component dependencies;
- `SensorStateComponent` owns the latest-sample state and lifecycle reset;
- `SensorSubscriberComponent` owns the `/sensor/value` subscription and updates the state;
- `WatchdogStatusPublisher` owns status publication;
- `WatchdogTimer` owns periodic freshness checks;
- before `activate`, `/sensor/status` stays silent and subscriber/timer work is gated while inactive;
- Lifecore gates subscriber callbacks, timer ticks, and publisher calls through component activation;
- `activate` logs `[watchdog_timer] watchdog timer started`, then allows `WAITING_FOR_FIRST_SAMPLE`, `OK value=<value>`, and `STALE age=<seconds>s` on `/sensor/status` and in `Watchdog status: ...` logs;
- `deactivate` logs `[watchdog_timer] watchdog timer stopped` and gates new status publication while resources remain configured;
- `cleanup` resets component state and releases the subscriber, publisher, and timer resources;
- the application node does not carry lifecycle flags or resource cleanup plumbing.

## Comparison Summary

| Variant | Best for | Lifecycle behavior | Main trade-off |
| --- | --- | --- | --- |
| Plain ROS 2 | prototypes | starts immediately | no configure/activate/deactivate control |
| Classic ROS 2 lifecycle | native managed nodes | lifecycle publisher is native | subscriptions, timers, and callback gating remain manual |
| lifecore_ros2 | component-oriented applications | subscriber, timer, and publisher behavior are lifecycle-gated through components | introduces a small composition layer |
