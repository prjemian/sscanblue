import datetime

import pytest

from ..utils import create_scan_id
from ._common import comparator
from ._common import get_context


@pytest.mark.parametrize(
    "raiser, reason",
    [
        [None, None],
    ],
)
def test_create_scan_id(raiser, reason):
    """Get suggested scan_id."""

    with get_context(raiser) as exinfo:
        scan_id = create_scan_id()
        assert isinstance(scan_id, int)

        dt: datetime.datetime = datetime.datetime.now()
        ours: int = (dt.hour * 100 + dt.minute) * 100 + dt.second
        assert ours - scan_id <= 1

    comparator(reason, exinfo)
