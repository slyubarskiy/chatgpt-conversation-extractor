"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "performance: marks tests as performance tests")


@pytest.fixture
def _isolated_config_env(tmp_path, monkeypatch):
    """Run config tests outside any real config file's reach.

    Without this, a user with ``~/.config/chatgpt_extractor/config.yaml``
    on disk would silently override the "no file found" assertion. We
    point HOME and CWD at an empty tmp_path and clear the env var.

    Shared across all tests that touch config loading. Originally lived in
    ``test_per_turn_timestamps.py``; promoted here on 2026-07-06 so the
    new web_urls config tests can share it without cross-file imports.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CHATGPT_EXTRACTOR_CONFIG", raising=False)
    return tmp_path
