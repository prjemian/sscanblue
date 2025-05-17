#!/usr/bin/env python

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
import datetime
import json
import logging
import pathlib
from typing import Any
from typing import Optional

import databroker
import pyRestTable
from apstools.callbacks import FileWriterCallbackBase
from apstools.callbacks import NXWriter
from apstools.callbacks import SpecWriterCallback2
from apstools.synApps.sscan import SscanRecord
from apstools.synApps.sscan import sscanDetector
from apstools.synApps.sscan import sscanPositioner
from apstools.synApps.sscan import sscanTrigger
from bluesky import RunEngine
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.callbacks.zmq import Publisher as ZmqPublisher
from ophyd import OphydObject
from ophyd.signal import EpicsSignalBase
from ophyd.status import Status

from . import __version__

bec: BestEffortCallback = BestEffortCallback()
cat: databroker.v2.Broker = None
DEFAULT_ZMQ_ADDRESS: str = "localhost:5567"
HINTED_STREAM: str = "primary"
logger: logging.Logger = None
metadata: dict = {}
RE: RunEngine = RunEngine()
scan: Optional[SscanRecord] = None
TEMPORARY_CATALOG_NAME: str = "temporary"

REPORTING_ERRORS: int = logging.ERROR
REPORTING_WARNING: int = logging.WARNING
REPORTING_INFO: int = logging.INFO
REPORTING_DEBUG: int = logging.DEBUG
REPORTING_BASIC: int = int((REPORTING_INFO + REPORTING_WARNING) / 2)
REPORTING_LEVELS: list[int] = [
    REPORTING_WARNING,  # default
    REPORTING_BASIC,  # -v
    REPORTING_INFO,  # -vv
    REPORTING_DEBUG,  # -vvv
]


class SscanConfigurationException(ValueError):
    """Problem with the sscan record configuration."""


class MySscanRecord(SscanRecord):
    """Local changes & fixes."""

    scan_mode: str = None  # LINEAR, TABLE, FLY

    def select_channels(self) -> None:
        """
        Select channels that are configured in EPICS.
        """
        for controller_name in "triggers positioners detectors".split():
            controller = getattr(self, controller_name)
            for channel_name in controller.component_names:
                channel = getattr(controller, channel_name)
                kind = "config" if controller_name == "triggers" else "hinted"
                channel.kind = kind if channel.defined_in_EPICS else "omitted"

    def learn_sscan_setup(self) -> None:
        self.select_channels()  # Per EPICS configuration.

        # Determine the scan mode.
        for p in self.positioners.component_names:
            pos: OphydObject = getattr(self.positioners, p)
            if self.scan_mode is None:
                self.scan_mode = pos.mode.get(as_string=True)
            if pos.mode.get(as_string=True) != self.scan_mode:
                self.scan_mode: Optional[str] = None
                raise SscanConfigurationException(
                    "All scan record positioners should use the same mode."
                )
            if self.scan_mode in ("LINEAR", "TABLE"):
                pos.array.kind = "omitted"
            else:
                pos.array.kind = "hinted"


def acquire_plan_sscan_1D(
    dwell: float = 0.001,
    md: Optional[dict[str, Any]] = None,
    **kwargs: Optional[dict[str, Any]],
):
    """plan: Run the sscan record configured for 1-D.."""

    sscan: SscanRecord = scan
    new_data: int = 0
    scanning: Status = Status()
    started: Status = Status()
    sscan.learn_sscan_setup()
    if sscan.scan_mode == "FLY":
        raise SscanConfigurationException("FLY scan not supported now.")

    # Add PV assignments to metadata.
    assignments: dict = {}
    detectors: list[str] = []
    positioners: list[str] = []
    for attr in sscan.read_attrs:

        def add_md(part) -> None:
            value: Any = part.get().strip()
            if len(value) > 0:
                assignments[part.name] = value

        obj: OphydObject = getattr(sscan, attr)
        if isinstance(obj, sscanDetector):
            add_md(obj.input_pv)
        elif isinstance(obj, sscanPositioner):
            add_md(obj.readback_pv)
            add_md(obj.setpoint_pv)
        elif isinstance(obj, sscanTrigger):
            add_md(obj.trigger_pv)
        elif isinstance(obj, EpicsSignalBase):
            field: str = obj.pvname.split(".")[-1]
            logger.debug(f"Renaming {obj.name=!r} to {field=!r}: {obj.kind=}")
            obj.name = field  # Rename for simpler reference
            if attr.startswith("detectors."):
                detectors.append(obj.name)
            elif attr.startswith("positioners."):
                positioners.append(obj.name)

    if len(detectors) == 0:
        raise SscanConfigurationException(f"{sscan.prefix!r} has no detectors.")
    if len(positioners) == 0:
        raise SscanConfigurationException(f"{sscan.prefix!r} has no positioners.")

    dt: datetime.datetime = datetime.datetime.now()
    _md: dict[str, Any] = {
        "assignments": assignments,
        "plan_name": "sscan_1D_plan",
        "datetime": dt.isoformat(),
        "scan_id": create_scan_id(),
        "hints": {"dimensions": [[["time"], HINTED_STREAM]]},
    }
    if len(detectors) > 0:
        logger.info("detectors: %r", detectors)
        _md["detectors"]: list[str] = detectors
    if len(positioners) > 0:
        logger.info("positioners: %r", positioners)
        _md["motors"]: list[str] = positioners
    _md.update(md or {})
    logger.info("Run metadata: %s", _md)

    if logger.getEffectiveLevel() < logging.WARNING:
        table: pyRestTable.Table = pyRestTable.Table()
        table.labels = ["signal or description", "source or value"]
        table.addRow(("scan mode", sscan.scan_mode))
        table.addRow(("number of points", sscan.number_points.get()))
        for k, v in assignments.items():
            table.addRow((k, v))
        print(table)

    def cb_phase(value=None, enum_strs=[], **kwargs) -> None:
        """Respond to CA monitor events of the sscan record phase."""
        nonlocal new_data

        if not started.done and value > 0:
            started.set_finished()
        phase: str = enum_strs[value]
        logger.debug("cb_phase()  phase=%r  started=%r", phase, started)
        if started.done:
            if phase == "RECORD SCALAR DATA":
                logger.debug("New sscan record data ready.")
                new_data += 1
            # elif phase == "IDLE":
            elif phase == "SCAN_DONE":
                logger.debug("Sscan record finished.")
                scanning.set_finished()

    @bpp.run_decorator(md=_md)
    def inner():
        nonlocal new_data

        logger.debug("Starting sscan execution.")
        yield from bps.mv(sscan.execute_scan, 1)  # Start the sscan.
        while not started.done:
            yield from bps.sleep(dwell)
        while not scanning.done or new_data > 0:
            if new_data > 0:
                new_data -= 1
                logger.debug("Create new event document.")
                yield from bps.create(HINTED_STREAM)
                yield from bps.read(sscan)
                yield from bps.save()
            yield from bps.sleep(dwell)
        logger.debug("Sscan finished.")

    try:
        sscan.scan_phase.subscribe(cb_phase)
        yield from inner()
    finally:
        phase: str = sscan.scan_phase.get(as_string=True, use_monitor=False)
        if phase != "IDLE":
            logger.error(f"Aborting {sscan.prefix!r}")
            yield from bps.mv(sscan.execute_scan, 0)
        sscan.scan_phase.clear_sub(cb_phase)


def create_scan_id() -> int:
    """
    Create a scan_id that is not likely to repeat quickly.

    This one uses the current HHMMSS.
    """
    dt: datetime.datetime = datetime.datetime.now()
    scan_id: int = (dt.hour * 100 + dt.minute) * 100 + dt.second
    return scan_id


def prepare_acquisition(parms: argparse.Namespace) -> None:
    """Setup this session to acquire sscan record data with Bluesky."""
    global cat, logger, metadata, nxwriter, scan, specwriter

    logger = logging.getLogger(__name__)
    logger.debug(f"{parms=!r}")
    if logger.getEffectiveLevel() < logging.WARNING:
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


def setup_logging(level_index) -> None:
    """Setup logging with selected configuration."""
    logging.addLevelName(REPORTING_BASIC, "BASIC")

    level_index = min(level_index or 0, len(REPORTING_LEVELS) - 1)
    logging.basicConfig(level=REPORTING_LEVELS[level_index])


def user_parameters() -> argparse.Namespace:
    """configure user's command line parameters from sys.argv"""
    doc: str = f"{__doc__.strip().splitlines()[0]}  v{__version__}"
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
        help=f"Run metadata (provided as JSON)",
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


if __name__ == "__main__":
    prepare_acquisition(user_parameters())

    # MUST call 'RE()' from __main__!
    (uid,) = RE(acquire_plan_sscan_1D(md=metadata))

    run = cat[uid]
    md = run.metadata["start"]
    logger.log(REPORTING_BASIC, "Run scan_id=%d", md["scan_id"])
    logger.log(REPORTING_BASIC, "Run uid=%r", md["uid"])
