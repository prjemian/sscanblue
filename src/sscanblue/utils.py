"""Miscellaneous functions."""
import argparse
import datetime
import json
import logging
import pathlib
from typing import Any

import bluesky
import databroker
from apstools.callbacks import NXWriter
from apstools.callbacks import SpecWriterCallback2
from apstools.synApps.sscan import SscanRecord
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.callbacks.zmq import Publisher as ZmqPublisher

from . import __version__
from .core import DEFAULT_ZMQ_ADDRESS
from .core import REPORTING_BASIC
from .core import TEMPORARY_CATALOG_NAME


def create_scan_id() -> int:
    """
    Create a scan_id that is not likely to repeat quickly.

    This one uses the current HHMMSS.
    """
    dt: datetime.datetime = datetime.datetime.now()
    scan_id: int = (dt.hour * 100 + dt.minute) * 100 + dt.second
    return scan_id


def prepare_acquisition(
    parms: argparse.Namespace,
    RE: bluesky.RunEngine,
) -> tuple[databroker.v2.Broker, SscanRecord, dict[str, Any]]:
    """Setup this session to acquire sscan record data with Bluesky."""
    from .core import TEMPORARY_CATALOG_NAME
    from .devices import MySscanRecord

    logger = logging.getLogger(__name__)
    logger.debug(f"{parms=!r}")
    if logger.getEffectiveLevel() < logging.WARNING:
        bec: BestEffortCallback = BestEffortCallback()
        RE.subscribe(bec)
        bec.disable_plots()

    logger.log(REPORTING_BASIC, f"{parms.metadata=!r}")
    metadata = json.loads(parms.metadata)

    scan = MySscanRecord(
        parms.pv_sscan,
        name="scan",
        kind="hinted",
    )
    logger.log(REPORTING_BASIC, "Sscan record PV: %r", scan.prefix)

    if parms.catalog_name == TEMPORARY_CATALOG_NAME:
        cat = databroker.temp().v2
    else:
        cat = databroker.catalog[parms.catalog_name].v2
    RE.subscribe(cat.v1.insert)
    logger.log(REPORTING_BASIC, "databroker catalog: %r", cat.name)

    if len(parms.nexus_file.strip()) > 0:
        nxwriter = NXWriter()
        nxwriter.warn_on_missing_content = False
        nxwriter.file_name = parms.nexus_file.strip()
        RE.subscribe(nxwriter.receiver)
        logger.log(
            REPORTING_BASIC,
            "Writing NeXus file: %r",
            nxwriter.file_name,
        )

    if len(parms.spec_file.strip()) > 0:
        specwriter = SpecWriterCallback2()
        specwriter.newfile(parms.spec_file.strip())
        RE.subscribe(specwriter.receiver)
        logger.log(
            REPORTING_BASIC,
            "Writing SPEC file: %r",
            specwriter.spec_filename,
        )

    RE.subscribe(ZmqPublisher(parms.zmq_addr))
    logger.log(REPORTING_BASIC, "ZMQ address %r", parms.zmq_addr)

    scan.wait_for_connection()
    return cat, scan, metadata


def setup_logging(level_index) -> None:
    """Setup logging with selected configuration, return level."""
    from .core import REPORTING_LEVELS

    logging.addLevelName(REPORTING_BASIC, "BASIC")

    level_index = min(level_index or 0, len(REPORTING_LEVELS) - 1)
    level: int = REPORTING_LEVELS[level_index]
    logging.basicConfig(level=level)


def sscan1blue_cli() -> argparse.Namespace:
    """configure user's command line parameters from sys.argv"""
    from . import __doc__ as pkg_doc
    doc: str = f"{pkg_doc.strip().splitlines()[0]}  v{__version__}"
    path: pathlib.Path = pathlib.Path(__file__)
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog=path.stem,
        description=doc,
    )
    parser.add_argument(
        "pv_sscan",
        action="store",
        help="PV of EPICS sscan record",
    )
    parser.add_argument(
        "-c",
        "--catalog",
        dest="catalog_name",
        action="store",
        default=TEMPORARY_CATALOG_NAME,
        help="Databroker catalog name (default: temporary catalog)",
    )
    parser.add_argument(
        "-m",
        "--metadata",
        dest="metadata",
        type=str,
        action="store",
        default="{}",
        help="Run metadata (provided as JSON)",
    )
    parser.add_argument(
        "-n",
        "--nexus_file",
        dest="nexus_file",
        action="store",
        default="",
        help="NeXus (HDF5) data file (default: no file)",
    )
    parser.add_argument(
        "-s",
        "--spec_file",
        dest="spec_file",
        action="store",
        default="",
        help="SPEC (text) data file (default: no file)",
    )
    parser.add_argument(
        "-v",
        "--log",
        dest="log_level",
        action="count",
        help=(
            "Log level. when omitted: quiet (only warnings and errors),"
            " -v: also data tables and run summary,"
            " -vv: also INFO-level messages,"
            " -vvv: verbose (also DEBUG-level messages)"
        ),
    )
    parser.add_argument(
        "-z",
        "--zmq_addr",
        dest="zmq_addr",
        action="store",
        default=DEFAULT_ZMQ_ADDRESS,
        help=f"ZMQ hostname:port (default: {DEFAULT_ZMQ_ADDRESS!r})",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=__version__,
    )

    return parser.parse_args()
