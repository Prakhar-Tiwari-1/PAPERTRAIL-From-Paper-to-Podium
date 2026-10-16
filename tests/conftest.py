import pytest

from papertrail.common import profile as profile_mod


@pytest.fixture(autouse=True)
def default_profile():
    """Every test starts with the empty default paper profile and cannot leak its own into the next test."""
    profile_mod.set_current(profile_mod.Profile())
    yield
    profile_mod.set_current(profile_mod.Profile())
