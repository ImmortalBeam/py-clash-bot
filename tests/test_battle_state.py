"""battle_state: one BGR frame -> elixir, units per lane, tower health."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pyclashbot.bot.battle_state import (
    BattleState,
    count_elixir_pips,
    emote_picker_open,
    lane_counts,
    read_battle_state,
    tower_hp_fraction,
    tower_standing,
    unit_bar_masks,
)
from pyclashbot.bot.coords import ENEMY_PRESENCE_MIN

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "battle"


def load(name: str) -> np.ndarray:
    im = cv2.imread(str(FIXTURES / f"{name}.png"))
    assert im is not None, name
    return im


def test_elixir_pips_counted_from_the_left() -> None:
    assert count_elixir_pips(load("t000_empty")) == 8
    assert count_elixir_pips(load("t126_enemy_tower_damaged")) == 5


def test_empty_arena_has_no_units_on_either_half() -> None:
    enemy, ours = unit_bar_masks(load("t000_empty"))
    assert max(lane_counts(enemy, "our")) < ENEMY_PRESENCE_MIN
    assert max(lane_counts(enemy, "their")) < ENEMY_PRESENCE_MIN
    assert max(lane_counts(ours, "their")) < ENEMY_PRESENCE_MIN


def test_enemy_push_on_our_left_is_seen_in_the_left_lane_only() -> None:
    enemy, ours = unit_bar_masks(load("t035_enemy_push_left"))
    left, right = lane_counts(enemy, "our")
    assert left >= ENEMY_PRESENCE_MIN
    assert right < ENEMY_PRESENCE_MIN
    assert max(lane_counts(ours, "our")) < ENEMY_PRESENCE_MIN  # our own units never count as enemy


def test_our_push_on_their_left_is_seen_as_ours_not_enemy() -> None:
    enemy, ours = unit_bar_masks(load("t078_our_push_left"))
    left, right = lane_counts(ours, "their")
    assert left >= ENEMY_PRESENCE_MIN
    assert max(lane_counts(enemy, "our")) < ENEMY_PRESENCE_MIN


def test_full_health_towers_read_near_one() -> None:
    im = load("t000_empty")
    for tower in ("our_L", "our_R", "their_L", "their_R"):
        hp = tower_hp_fraction(im, tower)
        assert hp is not None and hp >= 0.9, tower


def test_damaged_enemy_tower_reads_lower() -> None:
    hp = tower_hp_fraction(load("t126_enemy_tower_damaged"), "their_L")
    assert hp is not None and 0.55 <= hp <= 0.9  # on-screen 1984/2534 = 0.78; text overlaps the bar
    right = tower_hp_fraction(load("t126_enemy_tower_damaged"), "their_R")
    assert right is not None and right >= 0.9


def test_destroyed_tower_reads_none() -> None:
    im = load("t148_our_tower_destroyed")
    assert tower_standing(im, "our_L") is False
    assert tower_hp_fraction(im, "our_L") is None
    assert tower_standing(im, "our_R") is True
    right = tower_hp_fraction(im, "our_R")
    assert right is not None and right >= 0.9


def test_read_battle_state_assembles_everything() -> None:
    state = read_battle_state(load("t035_enemy_push_left"), elapsed=35.0)
    assert isinstance(state, BattleState)
    assert state.elapsed == 35.0
    assert state.threatened_lane() == "left"
    assert state.standing_towers("our") == 2
    assert state.standing_towers("their") == 2


def test_weakest_enemy_lane_prefers_the_damaged_tower() -> None:
    state = read_battle_state(load("t126_enemy_tower_damaged"), elapsed=126.0)
    assert state.weakest_enemy_lane() == "left"


def test_weakest_enemy_lane_is_none_when_both_towers_are_gone() -> None:
    state = BattleState(5, (0, 0), (0, 0), (0, 0), {"our_L": 1.0, "our_R": 1.0, "their_L": None, "their_R": None}, 10.0)
    assert state.weakest_enemy_lane() is None
    assert state.standing_towers("their") == 0


def test_enemy_standing_at_our_tower_is_still_detected() -> None:
    """Attackers stand on the tower footprint; excluding the whole footprint hid them."""
    enemy, _ = unit_bar_masks(load("t026_enemy_at_our_tower"))
    left, right = lane_counts(enemy, "our")
    assert left >= ENEMY_PRESENCE_MIN
    assert right < ENEMY_PRESENCE_MIN


def test_emote_picker_is_recognised_and_ignored() -> None:
    """The bot's own emote menu draws red king mouths across our half; it must not read as enemies."""
    assert emote_picker_open(load("t035_enemy_push_left")) is True
    assert emote_picker_open(load("t000_empty")) is False
    enemy, _ = unit_bar_masks(load("t035_enemy_push_left"))
    assert lane_counts(enemy, "our")[1] < ENEMY_PRESENCE_MIN


def test_tower_bar_is_found_when_its_row_shifts_a_few_pixels() -> None:
    """Second policy run, match 3: the bright fill row sat at y=92 instead of 94, so both
    full-health enemy towers read as 5% and the bot 'finished' them with Goblin Barrels."""
    im = load("t004_bar_row_offset")
    for tower in ("their_L", "their_R", "our_L", "our_R"):
        hp = tower_hp_fraction(im, tower)
        assert hp is not None and hp >= 0.9, tower
