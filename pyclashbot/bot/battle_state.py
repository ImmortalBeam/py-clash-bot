"""Pure readers that turn one in-battle screenshot (BGR, 633x419) into a BattleState.

Leaf module: imports only numpy, coords, state_detect (elixir pips) and image_rec.
Nothing here clicks or waits.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pyclashbot.bot.coords import (
    ARENA_LTRB,
    ENEMY_PRESENCE_MIN,
    LANE_SPLIT_X,
    RIVER_Y,
    TOWER_BADGE_BOXES,
    TOWER_BADGE_MIN_PIXELS,
    TOWER_BAR_MIN_PIXELS,
    TOWER_BOXES,
    TOWER_HP_BARS,
)
from pyclashbot.bot.state_detect import ELIXIR_COLOR, ELIXIR_COORDS
from pyclashbot.detection.image_rec import pixel_is_equal

TOWERS = ("our_L", "our_R", "their_L", "their_R")


@dataclass(frozen=True)
class BattleState:
    elixir: int
    enemy_our_half: tuple[int, int]  # (left, right) enemy unit-bar pixels on our half
    enemy_their_half: tuple[int, int]
    ours_their_half: tuple[int, int]
    tower_hp: dict[str, float | None]  # keys TOWERS; None = destroyed
    elapsed: float

    def threatened_lane(self) -> str | None:
        left, right = self.enemy_our_half
        if max(left, right) < ENEMY_PRESENCE_MIN:
            return None
        return "left" if left >= right else "right"

    def standing_towers(self, side: str) -> int:
        return sum(1 for key in (f"{side}_L", f"{side}_R") if self.tower_hp.get(key) is not None)

    def weakest_enemy_lane(self) -> str | None:
        candidates = [
            (hp, lane)
            for lane, key in (("left", "their_L"), ("right", "their_R"))
            if (hp := self.tower_hp.get(key)) is not None
        ]
        if not candidates:
            return None
        return min(candidates)[1]


def count_elixir_pips(iar: np.ndarray) -> int:
    count = 0
    for y, x in ELIXIR_COORDS:
        if not pixel_is_equal(iar[y][x], ELIXIR_COLOR, tol=65):
            break
        count += 1
    return count


def unit_bar_masks(iar: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Enemy (red) and friendly (blue) unit health-bar pixels inside the arena, towers excluded."""
    b = iar[..., 0].astype(int)
    g = iar[..., 1].astype(int)
    r = iar[..., 2].astype(int)
    enemy = (r > 185) & (g < 105) & (b < 105) & (r - g > 95)
    ours = (b > 185) & (r < 115) & (g > 100) & (g < 195)
    keep = np.zeros(iar.shape[:2], dtype=bool)
    left, top, right, bottom = ARENA_LTRB
    keep[top:bottom, left:right] = True
    for x1, y1, x2, y2 in TOWER_BOXES:
        keep[y1:y2, x1:x2] = False
    return enemy & keep, ours & keep


def lane_counts(mask: np.ndarray, half: str) -> tuple[int, int]:
    """(left, right) pixel counts of `mask` on the given half ("our" below the river, "their" above)."""
    _, top, _, bottom = ARENA_LTRB
    rows = mask[RIVER_Y:bottom] if half == "our" else mask[top:RIVER_Y]
    return int(rows[:, :LANE_SPLIT_X].sum()), int(rows[:, LANE_SPLIT_X:].sum())


def tower_standing(iar: np.ndarray, tower: str) -> bool:
    """The gold level badge next to the health bar is only drawn while the tower stands."""
    x1, y1, x2, y2 = TOWER_BADGE_BOXES[tower]
    box = iar[y1:y2, x1:x2].astype(int)
    gold = (box[..., 2] > 190) & (box[..., 1] > 140) & (box[..., 0] < 100)
    return int(gold.sum()) >= TOWER_BADGE_MIN_PIXELS


def tower_hp_fraction(iar: np.ndarray, tower: str) -> float | None:
    """Filled fraction of the princess-tower bar, or None when the tower is gone.

    The number printed over the bar hides part of the fill, so readings run ~0.1 low
    on damaged towers; callers should treat values as coarse (healthy / damaged / low).
    """
    if not tower_standing(iar, tower):
        return None
    y, x0, x1 = TOWER_HP_BARS[tower]
    row = iar[y, x0 : x1 + 1].astype(int)
    if tower.startswith("their"):
        filled = (row[:, 2] > 200) & (row[:, 0] > 100) & (row[:, 1] < 130)  # pink
    else:
        filled = (row[:, 0] > 200) & (row[:, 2] < 140) & (row[:, 1] > 120)  # blue
    idx = np.where(filled)[0]
    if len(idx) < TOWER_BAR_MIN_PIXELS:
        return 0.05  # standing but almost no bar visible: nearly dead
    return min(1.0, float(idx.max() + 1) / float(x1 - x0 + 1))


def read_battle_state(iar: np.ndarray, elapsed: float) -> BattleState:
    enemy, ours = unit_bar_masks(iar)
    return BattleState(
        elixir=count_elixir_pips(iar),
        enemy_our_half=lane_counts(enemy, "our"),
        enemy_their_half=lane_counts(enemy, "their"),
        ours_their_half=lane_counts(ours, "their"),
        tower_hp={tower: tower_hp_fraction(iar, tower) for tower in TOWERS},
        elapsed=elapsed,
    )
