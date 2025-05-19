"""Ophyd devices."""

import logging
from typing import Optional

from apstools.synApps.sscan import SscanRecord
from ophyd import Device

from .core import SscanConfigurationException

logger = logging.getLogger(__name__)


class MySscanRecord(SscanRecord):
    """Local changes & fixes."""

    scan_mode: Optional[str] = None  # LINEAR, TABLE, FLY

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
            pos: Device = getattr(self.positioners, p)
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
