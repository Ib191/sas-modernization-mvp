"""Shared pytest fixtures for build/tests/.

Locates the project root, ground_truth/, and build/target/output/ so each
test stub can be invoked individually.
"""
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def ground_truth_dir(project_root) -> Path:
    return project_root / "ground_truth"


@pytest.fixture(scope="session")
def target_output_dir(project_root) -> Path:
    return project_root / "build" / "target" / "output"
