"""Battle fixtures are real 419x633 BGR frames; geometry constants must agree with them."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from pyclashbot.bot.coords import ARENA_LTRB, LANE_SPLIT_X, RIVER_Y, TOWER_BOXES, TOWER_HP_BARS

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "battle"
NAMES = [
    "t000_empty",
    "t035_enemy_push_left",
    "t078_our_push_left",
    "t126_enemy_tower_damaged",
    "t148_our_tower_destroyed",
    "t026_enemy_at_our_tower",
    "t004_bar_row_offset",
    "t032_hog_at_our_tower",
    "t013_swarm_crossing_bridge",
]


def load(name: str) -> np.ndarray:
    im = cv2.imread(str(FIXTURES / f"{name}.png"))
    assert im is not None, name
    return im


@pytest.mark.parametrize("name", NAMES)
def test_fixture_is_full_frame(name) -> None:
    assert load(name).shape == (633, 419, 3)


def test_geometry_is_inside_the_frame() -> None:
    left, top, right, bottom = ARENA_LTRB
    assert 0 <= left < LANE_SPLIT_X < right <= 419
    assert 0 <= top < RIVER_Y < bottom <= 633
    for x1, y1, x2, y2 in TOWER_BOXES:
        assert 0 <= x1 < x2 <= 419 and 0 <= y1 < y2 <= 633
    for y, x0, x1 in TOWER_HP_BARS.values():
        assert 0 <= y < 633 and 0 <= x0 < x1 <= 419
