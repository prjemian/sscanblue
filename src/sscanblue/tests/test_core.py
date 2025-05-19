import pytest

from ..core import DEFAULT_ZMQ_ADDRESS
from ..core import HINTED_STREAM
from ..core import SscanConfigurationException
from ._common import comparator
from ._common import get_context


def test_constants():
    """Spot checks"""
    assert DEFAULT_ZMQ_ADDRESS == "localhost:5567"
    assert HINTED_STREAM == "primary"


@pytest.mark.parametrize(
    "raiser, reason",
    [
        [None, None],
        [SscanConfigurationException, "Problem"],
    ],
)
def test_SscanConfigurationException(raiser, reason):
    """Test the custom exception."""
    with get_context(raiser) as exinfo:
        if raiser is not None:
            raise raiser("Problem")

    comparator(reason, exinfo)
