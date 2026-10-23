"""Shared fixtures, for every test module."""

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """A runner for louvre's commands, in this process, with stdout and stderr kept apart."""
    return CliRunner()
