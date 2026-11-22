"""Broad-phase primitives for a 2-D physics world.

This module is the only place that contains the implementation.  Every
public function below honours the contract in its docstring.

Data model
----------
A box is a mapping with exactly the following shape::

    {
        "id": 7,                       # int, unique within one frame
        "min": (x0, y0),               # floats / ints
        "max": (x1, y1),               # x1 >= x0, y1 >= y0
    }

An AABB is *closed* for overlap/contact tests: ``[x0, x1]`` and ``[y0, y1]``.
Two boxes intersect when their closed projections overlap on both axes; merely
touching at an edge or corner counts as intersecting.  Geometry comparisons use
``TOL = 1e-9`` unless a function says otherwise.

Grid cells are different: cell ``(cx, cy)`` is the *half-open* region
``[cx * cell, (cx + 1) * cell) x [cy * cell, (cy + 1) * cell)``.  An AABB
therefore covers every cell whose region intersects its interior, and a right
edge that lies exactly on a cell boundary does not pull in the cell to its
right.

Every pair returned by this module is an unordered pair of ids, normalised to
``(min(a, b), max(a, b))``.  Pair lists are deduplicated and sorted
lexicographically so callers can compare them directly with ``==``.
"""

from __future__ import annotations

import math


TOL = 1e-9

#: Hard cap on the number of grid cells one AABB may cover.  Exceeding it is a
#: data/configuration error rather than a reason to allocate an unbounded list.
MAX_CELLS = 4096


def sort_endpoints(boxes: list[dict], axis: int) -> list[tuple[float, str, int]]:
    """Return the sorted SAP endpoints for ``boxes`` on ``axis``.

    ``axis`` is ``0`` for x and ``1`` for y.  Any other value raises
    ``ValueError``.

    The result contains exactly ``2 * len(boxes)`` entries of the form::

        (coordinate, kind, box_id)

    where ``kind`` is the string ``"min"`` or ``"max"``.  Entries are sorted by
    coordinate, then by kind with **all** ``"min"`` endpoints before all
    ``"max"`` endpoints at the same coordinate, then by ascending ``box_id``.
    Putting min before max at equal coordinates is what makes a box that only
    touches another box on this axis visible to the sweep.

    Coordinates are compared as exact values; ``TOL`` is not applied to the
    ordering (it is used by the overlap predicates).
    """
    if axis not in (0, 1):
        raise ValueError("axis must be 0 (x) or 1 (y)")

    endpoints = []
    for box in boxes:
        box_id = box["id"]
        endpoints.append((box["min"][axis], "min", box_id))
        endpoints.append((box["max"][axis], "max", box_id))

    # At equal coordinates every "min" precedes every "max" so touching boxes
    # remain visible to the sweep; ties of the same kind resolve by box id.
    endpoints.sort(key=lambda item: (item[0], 0 if item[1] == "min" else 1, item[2]))
    return endpoints


def sweep(boxes: list[dict], axis: int) -> list[tuple[int, int]]:
    """Return closed-interval axis-overlap candidates via sweep-and-prune.

    Only the projection on ``axis`` is considered; the other axis is ignored
    (this is the standard one-axis SAP broad phase).  Two boxes are candidates
    when their closed projections ``[min, max]`` overlap, including the case
    ``a.max == b.min``.

    The sweep must maintain an active set of ids while walking
    :func:`sort_endpoints`.  A ``"min"`` endpoint tests the arriving box against
    every currently active id and then adds the arriving box.  A ``"max"``
    endpoint removes that box.  Endpoint ties follow :func:`sort_endpoints`, so
    no touching pair is skipped and no box is removed before its own max
    endpoint.

    The returned list is normalised, deduplicated and lexicographically sorted,
    so each unordered pair occurs exactly once regardless of how many endpoints
    or active-set states produced it.  ``[]`` is returned for fewer than two
    boxes.  Duplicate box ids are not a supported input.
    """
    if axis not in (0, 1):
        raise ValueError("axis must be 0 (x) or 1 (y)")

    if len(boxes) < 2:
        return []

    pairs = set()
    active = set()
    for _coordinate, kind, box_id in sort_endpoints(boxes, axis):
        if kind == "min":
            for other_id in active:
                pairs.add((min(box_id, other_id), max(box_id, other_id)))
            active.add(box_id)
        else:
            active.discard(box_id)

    return sorted(pairs)


def hash_cells(box: dict, cell: float) -> list[tuple[int, int]]:
    """Return the grid cells covered by ``box`` using half-open cell regions.

    ``cell`` must be a finite, strictly positive number.  For a coordinate
    ``v`` the containing cell index is ``floor(v / cell)``.  With the cell
    region being half-open, the x indices are the half-open integer range::

        range(floor(x0 / cell), ceil(x1 / cell))

    and likewise for y.  Consequently an AABB whose right edge is exactly on a
    boundary does **not** include the cell to the right of that boundary, while
    a left edge exactly on a boundary includes that cell.  A degenerate AABB
    (``min == max``) still occupies the single cell containing the point.

    Cells are returned in lexicographic ``(cx, cy)`` order.  The number of
    cells is ``x_count * y_count``; if that count is greater than
    ``MAX_CELLS``, raise ``ValueError`` whose message contains ``"MAX_CELLS"``.
    The implementation must check this before materialising the list, so a
    pathological AABB cannot exhaust memory.  A non-positive or non-finite
    ``cell`` also raises ``ValueError``.
    """
    if not math.isfinite(cell) or cell <= 0:
        raise ValueError("cell must be a finite, strictly positive number")

    x0, y0 = box["min"]
    x1, y1 = box["max"]

    cx_lo = math.floor(x0 / cell)
    cx_hi = math.ceil(x1 / cell)
    if cx_hi <= cx_lo:
        # Degenerate (zero-width) extent: keep the single containing cell.
        cx_hi = cx_lo + 1

    cy_lo = math.floor(y0 / cell)
    cy_hi = math.ceil(y1 / cell)
    if cy_hi <= cy_lo:
        cy_hi = cy_lo + 1

    x_count = cx_hi - cx_lo
    y_count = cy_hi - cy_lo
    if x_count * y_count > MAX_CELLS:
        raise ValueError(
            f"cell coverage {x_count * y_count} exceeds MAX_CELLS={MAX_CELLS}"
        )

    return [
        (cx, cy)
        for cx in range(cx_lo, cx_hi)
        for cy in range(cy_lo, cy_hi)
    ]


def grid_pairs(boxes: list[dict], cell: float) -> list[tuple[int, int]]:
    """Return candidate pairs that share at least one grid cell.

    Every box is inserted into every cell from :func:`hash_cells`.  Each cell
    bucket must hold a *collection* of ids, not a single id: several boxes may
    occupy the same cell, and all ``C(n, 2)`` pairs among them are candidates.
    Distinct cells are distinct buckets even when their contents or ids look
    similar.

    This is a broad phase: candidates that share a cell need not actually
    intersect, so this function does not filter by AABB overlap.  The result is
    normalised, deduplicated and lexicographically sorted.  A pair sharing four
    cells appears once.  ``cell`` and the ``MAX_CELLS`` guard follow
    :func:`hash_cells`; ``[]`` is returned for fewer than two boxes.
    """
    if len(boxes) < 2:
        return []

    buckets: dict[tuple[int, int], list[int]] = {}
    for box in boxes:
        for grid_cell in hash_cells(box, cell):
            buckets.setdefault(grid_cell, []).append(box["id"])

    pairs = set()
    for occupants in buckets.values():
        for i in range(len(occupants)):
            for j in range(i + 1, len(occupants)):
                a, b = occupants[i], occupants[j]
                pairs.add((min(a, b), max(a, b)))

    return sorted(pairs)


def dedupe_pairs(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Normalise, deduplicate and sort unordered id pairs.

    Each incoming pair ``(a, b)`` is rewritten to ``(min(a, b), max(a, b))``.
    Thus ``(5, 2)`` and ``(2, 5)`` are the same pair and only one copy remains.
    Duplicates are removed after normalisation, and the resulting list is
    sorted lexicographically.  Self-pairs are *kept* here (as ``(i, i)``);
    rejecting them is :func:`validate_pairs`'s job.
    """
    return sorted({(min(a, b), max(a, b)) for a, b in pairs})


def incremental(
    prev_pairs: list[tuple[int, int]],
    moved_ids,
    boxes: list[dict],
    cell: float,
) -> list[tuple[int, int]]:
    """Update a previous candidate-pair set after some boxes moved.

    ``prev_pairs`` is the complete result for the previous frame.
    ``moved_ids`` is an iterable of ids whose AABBs may have changed.
    ``boxes`` describes the current frame.

    The returned list must equal ``grid_pairs(boxes, cell)`` whenever
    ``prev_pairs`` was a complete/valid result for the previous frame and only
    the listed ids moved.  In particular:

    * pairs whose two endpoints are both stationary may be reused from
      ``prev_pairs``;
    * every pair that touches a moved id is discarded, including pairs involving
      cells the box has just vacated, and is recomputed from the current cell
      coverage;
    * new pairs involving moved ids and stationary boxes are discovered.

    The result is normalised, deduplicated and sorted.  Implementations should
    touch only the cells affected by the moved ids; they must not leave stale
    pairs behind from the old cells.
    """
    moved = set(moved_ids)
    by_id = {box["id"]: box for box in boxes}

    # Stationary/stationary pairs are still valid: neither endpoint's cell
    # coverage changed.  Everything touching a moved id is dropped, which also
    # discards pairs from cells the moved boxes have just vacated.
    retained = {
        (min(a, b), max(a, b))
        for a, b in prev_pairs
        if a not in moved and b not in moved
    }

    # Recompute using only the cells the moved boxes currently cover.
    affected_cells = set()
    for box_id in moved:
        if box_id in by_id:
            affected_cells.update(hash_cells(by_id[box_id], cell))

    buckets: dict[tuple[int, int], list[int]] = {}
    for box in boxes:
        for grid_cell in hash_cells(box, cell):
            if grid_cell in affected_cells:
                buckets.setdefault(grid_cell, []).append(box["id"])

    recomputed = set()
    for occupants in buckets.values():
        for i in range(len(occupants)):
            for j in range(i + 1, len(occupants)):
                a, b = occupants[i], occupants[j]
                recomputed.add((min(a, b), max(a, b)))

    return sorted(retained | recomputed)


def validate_pairs(pairs: list[tuple[int, int]], boxes: list[dict]) -> list[str]:
    """Report malformed or geometrically impossible candidate pairs.

    Valid ids are the ids present in ``boxes``.  The input pairs are examined in
    order and at most one error string is produced per input pair, using the
    first applicable rule:

    1. Both ids equal: ``"self:{id}"``.
    2. An id is absent from ``boxes``: ``"unknown:{id}"`` (lowest absent id if
       both are absent).
    3. The normalised unordered pair was already seen: ``"duplicate:(a,b)"``.
    4. The two boxes' closed AABBs do not overlap on both axes:
       ``"disjoint:(a,b)"``.

    For rule 4, touching edges/corners count as intersecting.  The comparison
    allows a slack of ``TOL``: intervals intersect when
    ``a_max + TOL >= b_min`` and ``b_max + TOL >= a_min`` on both axes.  Rule 3
    uses normalised pairs, so ``(1, 2)`` followed by ``(2, 1)`` is a duplicate.

    Returns the error strings in input order (duplicates among error strings are
    not collapsed).  An empty list means every pair is well-formed, unique and
    at least touching.
    """
    by_id = {box["id"]: box for box in boxes}
    seen: set[tuple[int, int]] = set()
    errors = []

    for a, b in pairs:
        if a == b:
            errors.append(f"self:{a}")
            continue

        if a not in by_id or b not in by_id:
            absent = min(
                candidate
                for candidate in (a, b)
                if candidate not in by_id
            )
            errors.append(f"unknown:{absent}")
            continue

        normalised = (min(a, b), max(a, b))
        if normalised in seen:
            errors.append(f"duplicate:({normalised[0]},{normalised[1]})")
            continue
        seen.add(normalised)

        first = by_id[normalised[0]]
        second = by_id[normalised[1]]
        disjoint = False
        for axis in (0, 1):
            if not (
                first["max"][axis] + TOL >= second["min"][axis]
                and second["max"][axis] + TOL >= first["min"][axis]
            ):
                disjoint = True
                break
        if disjoint:
            errors.append(
                f"disjoint:({normalised[0]},{normalised[1]})"
            )

    return errors


def broadphase_batch(frames: list[list[dict]], config: dict) -> dict:
    """Compute candidates for each frame independently.

    ``config`` must contain ``"cell"`` (passed to :func:`grid_pairs`).  The
    return value is a mapping from frame index to that frame's normalised,
    deduplicated, sorted candidate list::

        {0: [...], 1: [...], ...}

    Frames are completely independent.  A cell bucket, id-to-cell map, active
    set, or any other grid state from one frame must not survive into the next;
    reusing it would make frame 2's result depend on frame 1's geometry.  An
    empty ``frames`` sequence returns ``{}``.
    """
    if not frames:
        return {}

    cell = config["cell"]
    return {
        frame_index: grid_pairs(frame, cell)
        for frame_index, frame in enumerate(frames)
    }
