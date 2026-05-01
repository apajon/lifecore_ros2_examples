# lifecore_ros2_examples

Applied, scenario-driven examples for [`lifecore_ros2`](https://github.com/apajon/lifecore_ros2).

This repository is a companion examples repository, not a reusable Python API. It hosts examples that are too domain-flavored, multi-node, or scenario-oriented for the core repository's small `examples/` directory.

## Scope

Examples belong here when they use applied ROS 2 patterns such as sensor pipelines, diagnostics aggregation, supervision, or multi-node orchestration. The core `lifecore_ros2/examples/` directory remains the place for minimal examples that teach one framework abstraction at a time.

This repository intentionally does not promise backward compatibility for example internals. Treat the examples as followable scaffolding, not a library surface.

Some future examples may take conceptual inspiration from MIT's [Underactuated Robotics](https://underactuated.mit.edu/) materials when choosing robotics dynamics, estimation, control, or systems scenarios. That source is used as design inspiration only; this repository does not vendor, mirror, or reproduce its content.

## Requirements

- Python 3.12+
- ROS 2 Jazzy available from the system installation
- `uv` for local commands
- A sibling checkout of `lifecore_ros2` at `../lifecore_ros2`

`rclpy` is intentionally not declared as a PyPI dependency. It is provided by the ROS 2 installation.

## Local Setup

From this repository:

```bash
uv sync --dev
```

The local `lifecore_ros2` dependency is resolved from the sibling checkout:

```text
../lifecore_ros2
```

## Validation

Run the local quality gates with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The GitHub Actions quality workflow is manual-only (`workflow_dispatch`). It does not run on every push, which keeps validation under deliberate control while the repository is being bootstrapped through small commits.

## Repository Layout

```text
examples/       Applied lifecycle examples
tests/          Smoke tests for examples and repository structure
```

## First Planned Example

The first applied scenario is planned as a sensor-fusion pipeline. It will demonstrate multiple simulated inputs, a lifecycle-aware fusion component, explicit warm-up behavior, and state reset on deactivate.
