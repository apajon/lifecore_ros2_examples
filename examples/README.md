# Examples

This directory hosts applied lifecycle examples for `lifecore_ros2`.

Each example should be executable as a standalone scenario and should document its lifecycle teaching axis in the module docstring or local README. Keep reusable library behavior in `lifecore_ros2`; keep scenario code here.

## Available Examples

- [`lifecycle_comparison/README.md`](lifecycle_comparison/README.md) compares plain ROS 2, classic ROS 2 lifecycle, and `lifecore_ros2` in the same sensor watchdog scenario. Use that README for the shared sensor publisher command, lifecycle transition commands, expected inactive gating behavior, and expected `/sensor/status` and log signals.
