"""Custom bluesky plans."""

import datetime
import logging
from typing import Any
from typing import Optional

import pyRestTable
from apstools.synApps import SscanRecord
from apstools.synApps.sscan import sscanDetector
from apstools.synApps.sscan import sscanPositioner
from apstools.synApps.sscan import sscanTrigger
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.utils import plan
from ophyd import OphydObject
from ophyd.signal import EpicsSignalBase
from ophyd.status import Status

from .core import HINTED_STREAM
from .core import SscanConfigurationException
from .utils import create_scan_id

logger = logging.getLogger(__name__)


@plan
def acquire_plan_sscan_1D(
    sscan: SscanRecord,
    dwell: float = 0.001,
    md: Optional[dict[str, Any]] = None,
    **kwargs: Optional[dict[str, Any]],
):
    """plan: Run the sscan record configured for 1-D.."""

    new_data: int = 0
    scanning: Status = Status()
    started: Status = Status()
    sscan.learn_sscan_setup()

    # Validate.
    if sscan.scan_mode == "FLY":
        raise SscanConfigurationException("FLY scan not supported now.")
    if len(sscan.read_attrs) == 0:
        raise SscanConfigurationException(
            f"Sscan record {sscan.prefix!r} not configured for scanning."
            # .
            " (No channels configured with EPICS PVs.)"
        )
    if sscan.number_points.get() == 0:
        raise SscanConfigurationException(
            f"No points to be collected. ({sscan.prefix}.NPTS=0)"
            # .
        )

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
        _md["detectors"] = detectors
    if len(positioners) > 0:
        logger.info("positioners: %r", positioners)
        _md["motors"] = positioners
    if md is not None:
        _md.update(md)
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
