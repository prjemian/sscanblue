import databroker
import ophyd.signal
import pytest
from apstools.synApps import SscanRecord
from bluesky import RunEngine

from ..devices import MySscanRecord
from ..plans import acquire_plan_sscan_1D
from ._common import comparator
from ._common import get_context


@pytest.mark.parametrize(
    "sscan, dwell, npts, raiser, reason",
    [
        [
            None,
            0.001,
            0,
            AttributeError,
            "'NoneType' object has no attribute 'connected'",
        ],
        [
            SscanRecord("", name="sscan"),
            0.001,
            0,
            AttributeError,
            "learn_sscan_setup",
        ],
        [
            MySscanRecord("", name="sscan"),
            0.001,
            0,
            ophyd.signal.ConnectionTimeoutError,
            "Failed to connect to .T1PV within 1.00 sec",
        ],
        [
            MySscanRecord("gp:scan1", name="sscan"),
            0.001,
            2,
            None,
            None,
        ],
    ],
)
def test_acquire_plan_sscan_1D(sscan, dwell, npts, raiser, reason):
    """Make the device, can't expect it connect."""

    with get_context(raiser) as exinfo:
        RE = RunEngine()

        if sscan.connected:
            sscan.number_points.put(npts)
            # TODO: configure the sscan record for a fast scan!
            cat = databroker.temp().v2
            RE.subscribe(cat.v1.insert)

        (uid,) = RE(acquire_plan_sscan_1D(sscan, dwell))
        assert isinstance(uid, str)

        if sscan.connected:
            run = cat.v1[uid]
            count = sum(
                [
                    1 if key == "event" else 0
                    for key, _doc  in run.documents()
                    # count the event documents
                ]
            )
            assert count == npts

    comparator(reason, exinfo)
