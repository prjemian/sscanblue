import pytest

from ..devices import MySscanRecord
from ._common import comparator
from ._common import get_context


@pytest.mark.parametrize(
    "prefix, raiser, reason",
    [
        ["IOC:scan1", None, None],
        [None, ValueError, "Must specify prefix if "],
    ],
)
def test_device(prefix, raiser, reason):
    """Make the device, can't expect it connect."""

    with get_context(raiser) as exinfo:
        scan = MySscanRecord(prefix, name="scan")
        assert not scan.connected
        assert scan.prefix == prefix
        assert scan.scan_mode is None

    comparator(reason, exinfo)
