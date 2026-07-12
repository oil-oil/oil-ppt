#!/usr/bin/env python3
"""Curated small template menu shown by the default contract."""
from __future__ import annotations


TIER1_TEMPLATES = (
    "cover", "end", "section", "comparison", "three-steps",
    "card-trio", "split-visual", "process-rail",
)
TIER1_SET = frozenset(TIER1_TEMPLATES)


def tier_of(template: str) -> int:
    return 1 if template in TIER1_SET else 2
