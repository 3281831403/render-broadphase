"""Red tests for the broad-phase exercise.

The module intentionally imports only the public stubs; every test calls at
least one stub and therefore fails with ``NotImplementedError`` in the initial
state.  The tests encode the contracts in ``broadphase/sap.py``.
"""

import pytest

from broadphase.sap import (
    broadphase_batch,
    dedupe_pairs,
    grid_pairs,
    hash_cells,
    incremental,
    sort_endpoints,
    sweep,
    validate_pairs,
    TOL,
)


def make_box(box_id, x0, y0, x1, y1):
    return {
        "id": box_id,
        "min": (float(x0), float(y0)),
        "max": (float(x1), float(y1)),
    }


def intersects(a, b):
    return (
        a["max"][0] + TOL >= b["min"][0]
        and b["max"][0] + TOL >= a["min"][0]
        and a["max"][1] + TOL >= b["min"][1]
        and b["max"][1] + TOL >= a["min"][1]
    )


def bruteforce_pairs(boxes):
    pairs = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if intersects(boxes[i], boxes[j]):
                a, b = boxes[i]["id"], boxes[j]["id"]
                pairs.append((min(a, b), max(a, b)))
    return sorted(pairs)


def axis_bruteforce(boxes, axis):
    pairs = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a["max"][axis] + TOL >= b["min"][axis] and b["max"][axis] + TOL >= a["min"][axis]:
                pairs.append((min(a["id"], b["id"]), max(a["id"], b["id"])))
    return sorted(pairs)


def test_01_endpoint_tie_orders_min_before_max_and_counts_touching_box():
    # Defect 1: sorting max before min at equal coordinates hides contact.
    boxes = [
        make_box(0, 0, 0, 1, 1),
        make_box(1, 1, 0, 2, 1),
    ]

    assert sort_endpoints(boxes, 0) == [
        (0.0, "min", 0),
        (1.0, "min", 1),
        (1.0, "max", 0),
        (2.0, "max", 1),
    ]
    assert sweep(boxes, 0) == [(0, 1)]


def test_02_active_set_expires_each_box_only_at_its_own_max():
    # Defect 2: a list/remove active set must not drop a live id when several
    # boxes share an endpoint coordinate and are retired together.
    boxes = [
        make_box(0, 0, 0, 3, 1),
        make_box(1, 1, 0, 3, 1),
        make_box(2, 2, 0, 3, 1),
        make_box(3, 1.5, 0, 4, 1),
    ]

    assert sweep(boxes, 0) == [
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (1, 3),
        (2, 3),
    ]


def test_03_sweep_returns_each_candidate_once_in_stable_order():
    # Defect 3: no duplicate pair and no dependence on endpoint/insertion order.
    boxes = [
        make_box(0, 0, 0, 3, 1),
        make_box(1, 1, 0, 4, 1),
        make_box(2, 2, 0, 5, 1),
        make_box(3, 3, 0, 6, 1),
    ]
    expected = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

    result = sweep(boxes, 0)
    assert result == expected
    assert result == sorted(set(result))


def test_04_hash_cells_excludes_cell_right_of_an_exact_max_edge():
    # Defect 4: int(x/cell) with an inclusive right edge adds a phantom cell.
    box = make_box(0, 0.5, 0.5, 2.0, 1.0)

    assert hash_cells(box, 1.0) == [(0, 0), (1, 0)]
    assert len(hash_cells(box, 1.0)) == 2


def test_05_hash_cells_rejects_cover_above_max_cells():
    # Defect 5: a huge AABB must not be expanded without a bound.
    huge = make_box(0, 0.0, 0.0, 100.0, 100.0)

    with pytest.raises(ValueError, match="MAX_CELLS"):
        hash_cells(huge, 1.0)


def test_06_grid_bucket_keeps_all_ids_sharing_one_cell():
    # Defect 6: one id per cell bucket overwrites earlier occupants.
    boxes = [
        make_box(0, 0.1, 0.1, 0.9, 0.9),
        make_box(1, 0.2, 0.2, 0.8, 0.8),
        make_box(2, 0.3, 0.3, 0.7, 0.7),
        make_box(9, 5.1, 5.1, 5.9, 5.9),
    ]

    assert grid_pairs(boxes, 1.0) == [(0, 1), (0, 2), (1, 2)]


def test_07_dedupe_normalises_reversed_and_repeated_pairs():
    # Defect 7: (a,b) and (b,a) are the same unordered pair.
    pairs = [(3, 1), (1, 3), (2, 0), (0, 2), (2, 2), (2, 2), (0, 1)]

    assert dedupe_pairs(pairs) == [(0, 1), (0, 2), (1, 3), (2, 2)]


def test_08_incremental_drops_stale_pair_from_vacated_cell():
    # Defect 8: recomputing only the moved box's new cells leaves its old pair.
    previous_boxes = [
        make_box(0, 0, 0, 1, 1),
        make_box(1, 1.5, 0, 2.5, 1),
    ]
    previous = grid_pairs(previous_boxes, 2.0)
    assert previous == [(0, 1)]

    current_boxes = [
        make_box(0, 10, 10, 11, 11),
        make_box(1, 1.5, 0, 2.5, 1),
    ]

    assert incremental(previous, [0], current_boxes, 2.0) == []


def test_09_validate_reports_disjoint_aabb_not_just_ids():
    # Defect 9: valid unique ids do not make a non-overlapping pair valid.
    boxes = [
        make_box(0, 0, 0, 1, 1),
        make_box(1, 2, 2, 3, 3),
        make_box(2, 0.5, 0.5, 1.5, 1.5),
    ]

    assert validate_pairs([(0, 1)], boxes) == ["disjoint:(0,1)"]
    assert validate_pairs([(0, 2)], boxes) == []
    assert validate_pairs([(0, 0)], boxes) == ["self:0"]
    assert validate_pairs([(0, 7)], boxes) == ["unknown:7"]
    assert validate_pairs([(2, 0), (0, 2)], boxes) == ["duplicate:(0,2)"]


def test_10_batch_does_not_reuse_first_frame_cell_mapping():
    # Defect 10: a cached grid from frame 0 leaks its pairs into frame 1.
    frames = [
        [make_box(0, 0.1, 0.1, 0.9, 0.9), make_box(1, 0.2, 0.2, 0.8, 0.8)],
        [make_box(0, 10.1, 10.1, 10.9, 10.9), make_box(1, 20.1, 20.1, 20.9, 20.9)],
    ]

    result = broadphase_batch(frames, {"cell": 1.0})

    assert result[0] == [(0, 1)]
    assert result[1] == []


def test_11_grid_pairs_matches_bruteforce_and_axis_sweep():
    # Additional: broad-phase result equals O(n^2) on a layout where cells and
    # geometry agree, so a permissive cell bucket cannot hide extra pairs.
    boxes = [
        make_box(0, 0.10, 0.10, 0.90, 0.90),
        make_box(1, 0.20, 0.20, 0.70, 0.70),
        make_box(2, 1.20, 0.10, 1.80, 0.90),
        make_box(3, 2.10, 2.10, 2.90, 2.90),
        make_box(4, 2.20, 2.20, 3.50, 3.50),
        make_box(5, 4.10, 4.10, 4.40, 4.40),
    ]

    expected = bruteforce_pairs(boxes)
    assert expected == [(0, 1), (3, 4)]
    assert grid_pairs(boxes, 1.0) == expected
    assert sweep(boxes, 0) == axis_bruteforce(boxes, 0)


def test_12_touching_boxes_are_candidates():
    # Additional: closed AABBs count edge contact as a candidate.
    boxes = [
        make_box(0, 0, 0, 1, 1),
        make_box(1, 0, 1, 1, 2),
    ]

    assert sweep(boxes, 0) == [(0, 1)]
    assert sweep(boxes, 1) == [(0, 1)]


def test_13_pairs_shared_across_multiple_cells_are_deduplicated():
    # Additional: one overlapping pair occupying four cells is still one pair.
    boxes = [
        make_box(0, 0, 0, 3, 3),
        make_box(1, 1, 1, 4, 4),
        make_box(2, 10, 10, 11, 11),
    ]

    pairs = grid_pairs(boxes, 2.0)
    assert pairs == [(0, 1)]
    assert pairs == sorted(set(pairs))


def test_14_incremental_result_equals_full_rebuild():
    # Additional: reuse of stationary pairs plus moved-cell recalculation must
    # be exactly equivalent to rebuilding the grid for the current frame.
    previous_boxes = [
        make_box(0, 0.1, 0.1, 0.9, 0.9),
        make_box(1, 0.2, 0.2, 0.8, 0.8),
        make_box(2, 0.3, 0.3, 0.7, 0.7),
        make_box(3, 9.1, 9.1, 9.6, 9.6),
    ]
    previous = grid_pairs(previous_boxes, 1.0)
    assert previous == [(0, 1), (0, 2), (1, 2)]

    current_boxes = [
        make_box(0, 5.1, 5.1, 5.8, 5.8),
        make_box(1, 0.2, 0.2, 0.8, 0.8),
        make_box(2, 0.3, 0.3, 0.7, 0.7),
        make_box(3, 0.1, 0.1, 0.6, 0.6),
    ]
    expected = grid_pairs(current_boxes, 1.0)
    assert expected == [(1, 2), (1, 3), (2, 3)]

    assert incremental(previous, [0, 3], current_boxes, 1.0) == expected


def test_15_batch_frames_equal_individual_grid_runs():
    # Additional: each frame is independent and matches its own standalone run.
    frames = [
        [make_box(0, 0.1, 0.1, 0.9, 0.9), make_box(1, 0.2, 0.2, 0.8, 0.8)],
        [make_box(0, 5.1, 5.1, 5.8, 5.8), make_box(1, 9.1, 9.1, 9.6, 9.6)],
        [
            make_box(0, 0.1, 0.1, 0.9, 0.9),
            make_box(1, 0.2, 0.2, 0.8, 0.8),
            make_box(2, 5.1, 5.1, 5.8, 5.8),
        ],
    ]

    result = broadphase_batch(frames, {"cell": 1.0})

    assert sorted(result) == [0, 1, 2]
    for frame_index, frame in enumerate(frames):
        assert result[frame_index] == grid_pairs(frame, 1.0)
    assert result[1] == []
