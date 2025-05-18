"""
Pre-configured EPICS/synApps sscan (1-D) executed by Bluesky.

Simplest case is the 1-D sscan since that makes the least assumptions (can use
`apstools.synApps.SscanRecord`).

User provides PV for the sscan record.  When user sets this support sets up the
ophyd and bluesky structures according to the EPICS configuration and starts a
run with its `RE`.  When the sscan.FAZE goes back to zero, the scan is done.
Data is captured either point-by-point (scan mode: `"LINEAR"` or `"TABLE"`) or
at scan end (scan mode: `"FLY"`).

For now, this code handles only LINEAR and TABLE modes.  Data is acquired
point-by-point.  No data arrays are collected from the sscan record.

LIVE DATA PLOT

To plot live data, first start these two processes in a separate console:

* ``nbs-viewer -d &`` (and open a new ZMQ data source)
  * Once started, choose "New Data Source", then "ZMQ"
* ``bluesky-0MQ-proxy 5567 5578``

EXAMPLE::

    sscan1blue.py gp:scan1 \
        -c my_data_catalog \
        -m '{"title": "test of sscan1blue", "scan_id": 25}' \
        -n nexus.h5 \
        -s spec.dat \
        -z localhost:5567 \
        -v
"""

import argparse
import logging
from typing import Any

from bluesky import RunEngine

from .core import REPORTING_BASIC
from .plans import acquire_plan_sscan_1D
from .utils import prepare_acquisition
from .utils import setup_logging
from .utils import sscan1blue_cli

parms: argparse.Namespace = sscan1blue_cli()
setup_logging(parms.log_level)
logger: logging.Logger = logging.getLogger(__name__)
RE: RunEngine = RunEngine()
cat, scan, metadata = prepare_acquisition(parms, RE)

# MUST call 'RE()' from __main__!
(uid,) = RE(acquire_plan_sscan_1D(scan, md=metadata))

if parms.log_level > 0:
    run: str = cat[uid]
    md: dict[str, Any] = run.metadata["start"]
    logger.log(REPORTING_BASIC, "Run scan_id=%d", md["scan_id"])
    logger.log(REPORTING_BASIC, "Run uid=%r", md["uid"])


def main():
    pass  # Must have a callable for an entry point.
