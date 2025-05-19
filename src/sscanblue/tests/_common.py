from contextlib import nullcontext as does_not_raise

import pytest


def comparator(expected, outcome):
    """Compare expected test reason with observed outcome."""
    if expected is None:
        assert outcome is None
    else:
        assert str(expected) in str(outcome)


def get_context(raiser):
    """Choose the context for testing."""
    if raiser is None:
        context = does_not_raise()
    else:
        if "warning" in str(raiser).lower():
            context = pytest.warns(raiser)
        else:
            context = pytest.raises(raiser)
    return context
