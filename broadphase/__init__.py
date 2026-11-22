"""Public surface for the broad-phase exercise."""

from .sap import (
    MAX_CELLS,
    TOL,
    broadphase_batch,
    dedupe_pairs,
    grid_pairs,
    hash_cells,
    incremental,
    sort_endpoints,
    sweep,
    validate_pairs,
)

__all__ = [
    "MAX_CELLS",
    "TOL",
    "broadphase_batch",
    "dedupe_pairs",
    "grid_pairs",
    "hash_cells",
    "incremental",
    "sort_endpoints",
    "sweep",
    "validate_pairs",
]
