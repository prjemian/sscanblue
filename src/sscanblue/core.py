"""Core definitions."""

import logging


class SscanConfigurationException(ValueError):
    """Problem with the sscan record configuration."""


DEFAULT_ZMQ_ADDRESS: str = "localhost:5567"
HINTED_STREAM: str = "primary"

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

TEMPORARY_CATALOG_NAME: str = "temporary"
