"""battle_policy: pure decisions from a BattleState and the hand."""

from __future__ import annotations

from pyclashbot.bot.battle_policy import (
    CHIP_MIN_ELIXIR,
    HandCard,
    PushMemory,
    attack_threshold,
    choose_slot,
    decide,
    game_mode,
    role_for_group,
)
from pyclashbot.bot.battle_state import BattleState

FULL = {"our_L": 1.0, "our_R": 1.0, "their_L": 1.0, "their_R": 1.0}


def state(elixir=8, enemy_our=(0, 0), ours_their=(0, 0), hp=None, elapsed=60.0) -> BattleState:
    return BattleState(elixir, enemy_our, (0, 0), ours_their, dict(hp or FULL), elapsed)


HAND = [
    HandCard(0, "knight", "tank"),
    HandCard(1, "musketeer", "support"),
    HandCard(2, "cannon", "building"),
    HandCard(3, "zap", "small_spell"),
]


def test_roles_come_from_placement_groups() -> None:
    assert role_for_group("bridge_line") == "tank"
    assert role_for_group("bridge_rush") == "win_condition"
    assert role_for_group("back_support") == "support"
    assert role_for_group("defense_building") == "building"
    assert role_for_group("reactive_spell") == "small_spell"
    assert role_for_group("large_spell") == "big_spell"
    assert role_for_group("goblin_barrel") == "chip"
    assert role_for_group("No group") == "support"


def test_game_mode_from_standing_towers() -> None:
    assert game_mode(state()) == "even"
    assert game_mode(state(hp={**FULL, "their_L": None})) == "ahead"
    assert game_mode(state(hp={**FULL, "our_R": None})) == "behind"
    assert game_mode(state(hp={**FULL, "our_R": None, "their_L": None})) == "even"


def test_attack_threshold_by_mode_and_time() -> None:
    assert attack_threshold("ahead", 60.0) == 9
    assert attack_threshold("even", 60.0) == 8
    assert attack_threshold("behind", 60.0) == 7
    assert attack_threshold("even", 130.0) == 7  # double elixir: one less
    assert attack_threshold("even", 160.0) == 5  # last 30 s, not ahead
    assert attack_threshold("ahead", 160.0) == 8  # last 30 s, ahead: only the endgame discount


def test_defend_beats_everything_when_enemies_are_on_our_half() -> None:
    d = decide(state(elixir=10, enemy_our=(80, 0)), HAND, None)
    assert d.kind == "defend" and d.lane == "left" and d.zone == "defense"
    assert d.roles[0] == "building" and d.min_elixir == 0


def test_hold_when_below_attack_threshold_and_nothing_to_do() -> None:
    d = decide(state(elixir=6), HAND, None)
    assert d.kind == "hold" and d.min_elixir == 8


def test_attack_targets_the_weakest_enemy_tower_at_threshold() -> None:
    d = decide(state(elixir=8, hp={**FULL, "their_R": 0.4}), HAND, None)
    assert d.kind == "attack" and d.lane == "right" and d.zone == "bridge"
    assert d.roles == ("tank", "win_condition")


def test_follow_up_after_a_recent_tank_play() -> None:
    d = decide(state(elixir=4, elapsed=50.0), HAND, PushMemory("left", started_at=45.0))
    assert d.kind == "follow_up" and d.lane == "left" and d.zone == "support_behind"
    assert d.roles == ("support",)


def test_follow_up_expires_after_the_window() -> None:
    d = decide(state(elixir=4, elapsed=60.0), HAND, PushMemory("left", started_at=45.0))
    assert d.kind == "hold"


def test_finish_low_tower_with_big_spell_or_chip() -> None:
    hand = [*HAND[:2], HandCard(2, "fireball", "big_spell"), HAND[3]]
    d = decide(state(elixir=4, hp={**FULL, "their_L": 0.1}), hand, None)
    assert d.kind == "finish" and d.lane == "left" and d.zone == "spell_tower"


def test_chip_when_clear_and_affordable() -> None:
    hand = [HandCard(0, "goblin_barrel", "chip"), *HAND[1:]]
    d = decide(state(elixir=CHIP_MIN_ELIXIR), hand, None)
    assert d.kind == "chip" and d.zone == "chip"


def test_no_attack_when_no_enemy_tower_lane_is_known() -> None:
    d = decide(state(elixir=10, hp={**FULL, "their_L": None, "their_R": None}), HAND, None)
    assert d.kind == "hold"


def test_choose_slot_follows_role_order_then_avoids_recent() -> None:
    hand = [HandCard(0, "musketeer", "support"), HandCard(1, "archers", "support"), HandCard(2, "knight", "tank")]
    assert choose_slot(hand, ("tank", "support"), recent=[]) == hand[2]
    assert choose_slot(hand, ("support",), recent=[0]) == hand[1]
    assert choose_slot(hand, ("building",), recent=[]) is None
