"""Smoke test confirming the package imports and the scaffold is wired correctly.

Replace/extend as real modules land. The full suite should mirror the Java tests in
../dpp-sdk-platform (round-trip, edge cases, inbound validation, end-to-end scenarios).
"""

import dpp_sdk


def test_package_version() -> None:
    assert isinstance(dpp_sdk.__version__, str)
    assert dpp_sdk.__version__.count(".") >= 2


def test_subpackages_importable() -> None:
    import dpp_sdk.clients  # noqa: F401
    import dpp_sdk.core  # noqa: F401
    import dpp_sdk.dpp4fun  # noqa: F401
