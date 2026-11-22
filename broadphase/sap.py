"""Broad-phase primitives for a 2-D physics world.

This module is the only place that should contain the implementation.  Every
public function below is a stub: it raises ``NotImplementedError`` until the
contract in its docstring is implemented.

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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


def dedupe_pairs(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Normalise, deduplicate and sort unordered id pairs.

    Each incoming pair ``(a, b)`` is rewritten to ``(min(a, b), max(a, b))``.
    Thus ``(5, 2)`` and ``(2, 5)`` are the same pair and only one copy remains.
    Duplicates are removed after normalisation, and the resulting list is
    sorted lexicographically.  Self-pairs are *kept* here (as ``(i, i)``);
    rejecting them is :func:`validate_pairs`'s job.
    """
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError
