"""The package imports and reports the installed distribution version."""

from importlib.metadata import version

import aisim


def test_version_matches_distribution() -> None:
    assert aisim.__version__ == version("ai-it-labour-sim")
