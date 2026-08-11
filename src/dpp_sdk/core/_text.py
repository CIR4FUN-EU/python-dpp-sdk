"""Stable internal text predicates for approved cross-language contracts."""

from __future__ import annotations

_CONTRACT_WHITESPACE = frozenset(
    chr(code_point)
    for code_point in (
        *range(0x0009, 0x000E),
        0x0020,
        0x0085,
        0x00A0,
        0x1680,
        *range(0x2000, 0x200B),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    )
)


def is_blank(value: str | None) -> bool:
    """Return whether ``value`` contains only the frozen whitespace table."""
    return value is None or not value or all(char in _CONTRACT_WHITESPACE for char in value)


def strip_contract_whitespace(value: str) -> str:
    """Strip only the frozen contract whitespace table from both ends."""
    start = 0
    end = len(value)
    while start < end and value[start] in _CONTRACT_WHITESPACE:
        start += 1
    while end > start and value[end - 1] in _CONTRACT_WHITESPACE:
        end -= 1
    return value[start:end]


def normalize_for_comparison(value: str) -> str:
    """Return locale-independent lowercase text after contract-table trimming."""
    return strip_contract_whitespace(value).lower()
