# lifecore_ros2_examples

Scenario-driven ROS 2 examples for comparing raw `rclpy`, native lifecycle nodes, and [`lifecore_ros2`](https://github.com/apajon/lifecore_ros2) component-oriented lifecycle composition.

If you have ever duplicated activation flags, timer guards, callback guards, and cleanup code inside a ROS 2 lifecycle node, this repository shows the problem and one component-oriented way to structure it. In the `lifecore_ros2` variants, application hooks such as `on_message` and `on_tick` stay explicit while the framework keeps lifecycle gating and resource ownership.

The main comparison focuses on inactive runtime misuse: when a lifecycle node is configured but not active, or has been deactivated, incoming samples should not update watchdog state, timer-driven status publication should not happen, and the node should keep running without treating the misuse as a new exception policy.

This is a companion examples repository, not a reusable Python API. It hosts applied examples that are too domain-flavored, multi-node, or scenario-oriented for the core repository's small `examples/` directory.

## What this repository is for

Use this repository when you want to compare lifecycle-aware ROS 2 composition styles on the same runnable scenario, rather than reading minimal API walkthroughs.

## What this repository is not

- not a second reusable library
- not the main documentation entry point for `lifecore_ros2`
- not a stable API surface for scenario internals

`lifecore_ros2` does not replace the native ROS 2 lifecycle state machine. It keeps the node lifecycle native and adds a small component ownership layer inside the node.

## Quick Run

Clone the repository, sync the environment, and run the `lifecore_ros2` variant of the comparison:

```bash
git clone https://github.com/apajon/lifecore_ros2_examples.git
cd lifecore_ros2_examples
source /opt/ros/jazzy/setup.bash
uv sync --dev

# Terminal 1
source /opt/ros/jazzy/setup.bash
uv run python examples/lifecycle_comparison/sensor_value_publisher_node.py

# Terminal 2
source /opt/ros/jazzy/setup.bash
uv run python examples/lifecycle_comparison/lifecore_ros2/sensor_watchdog_lifecore_node.py

# Terminal 3
source /opt/ros/jazzy/setup.bash
ros2 lifecycle set /sensor_watchdog_lifecore configure
ros2 lifecycle set /sensor_watchdog_lifecore activate
ros2 topic echo /sensor/status
```

Then open [`examples/lifecycle_comparison/README.md`](examples/lifecycle_comparison/README.md) to run the plain ROS 2 and classic lifecycle variants side by side.

## Scope

Examples belong here when they use applied ROS 2 patterns such as sensor pipelines, diagnostics aggregation, supervision, or multi-node orchestration. The core `lifecore_ros2/examples/` directory remains the place for minimal examples that teach one library abstraction at a time.

This repository intentionally does not promise backward compatibility for example internals. Treat the examples as runnable learning material, not as a stable import surface.

Future examples may use robotics dynamics, estimation, control, or systems scenarios inspired by MIT's [Underactuated Robotics](https://underactuated.mit.edu/) materials, without vendoring or reproducing their content.

## Requirements

- Python 3.12+
- ROS 2 Jazzy available from the system installation
- `uv` for local commands

`rclpy` is intentionally not declared as a PyPI dependency. It is provided by the ROS 2 installation.
`lifecore_ros2` is resolved from the published PyPI package by default.

## Local Setup

From this repository:

```bash
source /opt/ros/jazzy/setup.bash
uv sync --dev
```

To test examples against an unreleased local checkout of the core repository,
temporarily override the dependency with an editable path:

```bash
uv add --editable ../lifecore_ros2
```

## Validation

Run the local quality gates with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

CI runs on pull requests to `main` and can also be triggered manually. The separate `quality.yml` workflow remains manual-only for deliberate ad-hoc validation.

## Repository Layout

```text
examples/       Applied lifecycle examples
tests/          Smoke tests for examples and repository structure
```

## Available Examples

- [`examples/lifecycle_comparison/README.md`](examples/lifecycle_comparison/README.md) compares plain ROS 2, classic ROS 2 lifecycle, and `lifecore_ros2` in the same sensor watchdog scenario. It includes the shared sensor publisher command, the commands to run each variant, the expected `/sensor/status` and log signals, and the split between public component hooks and framework-managed lifecycle gating.

## Planned Examples

- Sensor-fusion pipeline with multiple simulated inputs, a lifecycle-aware fusion component, explicit warm-up behavior, and state reset on deactivate.
