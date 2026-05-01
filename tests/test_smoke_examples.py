"""Smoke tests for the examples repository bootstrap."""

import pathlib
import runpy

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"


def _example_modules() -> list[pathlib.Path]:
    return sorted(path for path in EXAMPLES_DIR.rglob("*.py") if path.name != "__init__.py")


def test_examples_directory_exists() -> None:
    """The companion repository reserves an examples directory from the start."""
    assert EXAMPLES_DIR.is_dir()


@pytest.mark.parametrize(
    "module_path",
    _example_modules(),
    ids=lambda module_path: str(module_path.relative_to(EXAMPLES_DIR)),
)
def test_example_modules_import_without_running_main(module_path: pathlib.Path) -> None:
    """Example modules should be import-safe before their main routines run."""
    module_globals = runpy.run_path(
        str(module_path),
        run_name=f"lifecore_ros2_examples_smoke.{module_path.stem}",
    )

    assert module_globals
