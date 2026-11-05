import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content.loader import load_content  # noqa: E402
from app.engine.rules import load_rules_config  # noqa: E402
from app.engine.state import new_state  # noqa: E402


@pytest.fixture(scope="session")
def content():
    return load_content()


@pytest.fixture(scope="session")
def world(content):
    return content.world


@pytest.fixture(scope="session")
def cfg():
    return load_rules_config()


@pytest.fixture
def state(world):
    return new_state(world, seed=834201, lang="en")
