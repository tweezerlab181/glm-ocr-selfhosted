from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_pdf() -> Path:
    return FIXTURES / "sample.pdf"


@pytest.fixture
def sample_png() -> Path:
    return FIXTURES / "sample.png"
