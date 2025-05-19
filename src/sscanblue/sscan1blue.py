"""Pre-configured EPICS/synApps sscan (1-D) executed by Bluesky."""

import argparse
import logging
from typing import Any

from bluesky import RunEngine

from .core import REPORTING_BASIC
from .core import TEMPORARY_CATALOG_NAME
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
    if cat.name != TEMPORARY_CATALOG_NAME:
        logger.log(REPORTING_BASIC, "Run uid=%r", md["uid"])


def main():
    """Required callable for an entry point."""
    pass
