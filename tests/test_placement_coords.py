"""Troop placement: tanks at the bridge, support just behind it, fallback forward.

Arena geometry at 419x633: the river is at y ~255-275, the player's half starts at
y ~283 (the bridge foot), princess towers sit at y ~385-410. The bot plays on a
timer with no reaction logic, so troops dropped deep in the back field spend the
match walking; every troop group is expected to start at or just behind the bridge.
"""

from __future__ import annotations

import random

import pytest

from pyclashbot.bot.card_detection import PLAY_COORDS, calculate_play_coords, zone_play_coords

BRIDGE_Y = (281, 292)  # bridge foot, same band the bridge_rush group uses
BEHIND_BRIDGE_Y = (300, 330)  # one to two tiles behind the bridge
FALLBACK_Y = (285, 330)
LANE_X = {"left": (60, 206), "right": (210, 351)}


def _in(value: int, band: tuple[int, int]) -> bool:
    return band[0] <= value <= band[1]


@pytest.mark.parametrize("side", ["left", "right"])
def test_bridge_line_troops_start_at_the_bridge(side) -> None:
    for x, y in PLAY_COORDS["bridge_line"][side]:
        assert _in(y, BRIDGE_Y), (x, y)
        assert _in(x, LANE_X[side]), (x, y)


@pytest.mark.parametrize("group", ["back_support", "king_lane"])
@pytest.mark.parametrize("side", ["left", "right"])
def test_support_troops_start_just_behind_the_bridge(group, side) -> None:
    for x, y in PLAY_COORDS[group][side]:
        assert _in(y, BEHIND_BRIDGE_Y), (group, x, y)
        assert _in(x, LANE_X[side]), (group, x, y)


@pytest.mark.parametrize("elapsed", [0, 30, 100, 250])
@pytest.mark.parametrize("side", ["left", "right"])
def test_unrecognised_cards_are_played_forward_at_any_time(elapsed, side) -> None:
    random.seed(1234)
    for _ in range(50):
        x, y = calculate_play_coords("No group", side, elapsed)
        assert _in(y, FALLBACK_Y), (elapsed, x, y)
        assert _in(x, LANE_X[side]), (elapsed, x, y)


def test_calculate_play_coords_uses_the_table_for_known_groups() -> None:
    random.seed(1)
    coord = calculate_play_coords("bridge_line", "left")
    assert coord in PLAY_COORDS["bridge_line"]["left"]


def test_non_troop_groups_are_unchanged() -> None:
    """Spells, buildings and tunnelling cards keep their tuned spots."""
    assert PLAY_COORDS["defense_building"]["left"][0] == (224, 320)
    assert PLAY_COORDS["lane_spell"] == {"left": [(118, 185)], "right": [(295, 185)]}
    assert PLAY_COORDS["goblin_barrel"]["left"] == [(115, 161), (116, 161), (117, 161)]
    assert PLAY_COORDS["miner"]["right"][0] == (274, 152)
    assert PLAY_COORDS["bridge_rush"]["left"] == [(77, 281), (113, 286), (154, 283)]


def test_defense_zone_is_in_front_of_our_towers() -> None:
    for side in ("left", "right"):
        for x, y in PLAY_COORDS["defense"][side]:
            assert 330 <= y <= 360, (side, x, y)
            assert _in(x, LANE_X[side]), (side, x, y)


def test_zone_lookup_routes_by_zone_and_card_group() -> None:
    random.seed(7)
    assert zone_play_coords("defense", "left", "bridge_line") in PLAY_COORDS["defense"]["left"]
    assert zone_play_coords("defense", "right", "reactive_spell") in PLAY_COORDS["spell_defense"]["right"]
    assert zone_play_coords("support_behind", "left", "back_support") in PLAY_COORDS["back_support"]["left"]
    assert zone_play_coords("bridge", "right", "bridge_line") in PLAY_COORDS["bridge_line"]["right"]
    assert zone_play_coords("bridge", "left", "bridge_rush") in PLAY_COORDS["bridge_rush"]["left"]
    assert zone_play_coords("chip", "left", "goblin_barrel") in PLAY_COORDS["goblin_barrel"]["left"]
    assert zone_play_coords("spell_tower", "right", "large_spell") in PLAY_COORDS["large_spell"]["right"]
    assert zone_play_coords("none", "left", "bridge_line") is None
