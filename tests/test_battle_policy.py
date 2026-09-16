"""battle_policy: pure decisions from a BattleState and the hand."""

from __future__ import annotations

from pyclashbot.bot.battle_policy import (
    CHIP_MIN_ELIXIR,
    DEFEND_COOLDOWN_S,
    FINISH_MIN_ELAPSED_S,
    OPENING_S,
    PUSH_COOLDOWN_S,
    THREAT_LARGE,
    THREAT_MEDIUM,
    THREAT_TRIVIAL,
    DefendMemory,
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


def test_both_enemy_towers_down_means_attack_the_king_through_our_standing_lane() -> None:
    """Match 7 of the policy run: 2-2 in overtime, both enemy princess towers gone, the bot
    held at 10 elixir with no target while the opponent took our king."""
    d = decide(state(elixir=10, hp={**FULL, "their_L": None, "their_R": None}), HAND, None)
    assert d.kind == "attack" and d.lane == "left"
    d = decide(state(elixir=10, hp={**FULL, "their_L": None, "their_R": None, "our_L": None}), HAND, None)
    assert d.kind == "attack" and d.lane == "right"


def test_choose_slot_follows_role_order_then_avoids_recent() -> None:
    hand = [HandCard(0, "musketeer", "support"), HandCard(1, "archers", "support"), HandCard(2, "knight", "tank")]
    assert choose_slot(hand, ("tank", "support"), recent=[]) == hand[2]
    assert choose_slot(hand, ("support",), recent=[0]) == hand[1]
    assert choose_slot(hand, ("building",), recent=[]) is None


def test_no_chip_right_after_a_push_even_with_elixir() -> None:
    """Dumping a chip card on top of a push left the bot at 2 elixir for the counter-push."""
    hand = [HandCard(0, "goblin_barrel", "chip"), HandCard(1, "musketeer", "support")]
    recent_push = PushMemory("left", started_at=60.0 - 10.0)  # past the follow-up window, inside the cooldown
    d = decide(state(elixir=CHIP_MIN_ELIXIR, elapsed=60.0), hand, recent_push)
    assert d.kind == "hold"


def test_chip_allowed_once_the_push_cooldown_has_passed() -> None:
    hand = [HandCard(0, "goblin_barrel", "chip"), HandCard(1, "musketeer", "support")]
    old_push = PushMemory("left", started_at=60.0 - PUSH_COOLDOWN_S - 1)
    d = decide(state(elixir=CHIP_MIN_ELIXIR, elapsed=60.0), hand, old_push)
    assert d.kind == "chip"


def test_chip_needs_a_cushion_of_elixir() -> None:
    assert CHIP_MIN_ELIXIR >= 7


def test_no_finish_in_the_opening_seconds() -> None:
    """A tower cannot be near death at 1 s; an early low reading is a misread, not a target."""
    hand = [*HAND[:2], HandCard(2, "fireball", "big_spell"), HAND[3]]
    d = decide(state(elixir=4, hp={**FULL, "their_L": 0.05}, elapsed=FINISH_MIN_ELAPSED_S - 1), hand, None)
    assert d.kind != "finish"
    d = decide(state(elixir=4, hp={**FULL, "their_L": 0.05}, elapsed=FINISH_MIN_ELAPSED_S + 1), hand, None)
    assert d.kind == "finish"


def test_tower_under_fire_without_visible_enemies_is_defended() -> None:
    """Balloons and spells hurt a tower with little or no health bar on our half."""
    d = decide(state(elixir=3), HAND, None, under_fire="left")
    assert d.kind == "defend" and d.lane == "left"
    d = decide(state(elixir=3), HAND, None, under_fire=None)
    assert d.kind == "hold"


CHEAP_HAND = [
    HandCard(0, "electro_spirit", "support"),
    HandCard(1, "witch", "support"),
    HandCard(2, "cannon", "building"),
    HandCard(3, "fireball", "small_spell"),
]


def test_trivial_threat_is_left_to_the_tower() -> None:
    """Overnight: 40% of defends answered fewer than 30 enemy pixels, one small unit."""
    d = decide(state(elixir=5, enemy_our=(THREAT_TRIVIAL - 1, 0)), CHEAP_HAND, None)
    assert d.kind != "defend"


def test_small_threat_gets_only_a_cheap_card() -> None:
    d = decide(state(elixir=5, enemy_our=(THREAT_MEDIUM - 1, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and d.lane == "left"
    assert d.roles == ("cheap",)


def test_medium_threat_gets_building_support_or_cheap_but_no_spell() -> None:
    d = decide(state(elixir=5, enemy_our=(THREAT_LARGE - 1, 0)), CHEAP_HAND, None)
    assert d.kind == "defend"
    assert "small_spell" not in d.roles and "building" in d.roles and "cheap" in d.roles


def test_large_threat_allows_tank_and_spell() -> None:
    d = decide(state(elixir=5, enemy_our=(THREAT_LARGE + 50, 0)), CHEAP_HAND, None)
    assert d.kind == "defend"
    assert "tank" in d.roles and "small_spell" in d.roles


def test_same_lane_is_not_defended_again_within_the_cooldown_unless_the_threat_grew() -> None:
    """Overnight: half of all defends repeated the same lane within 6 s."""
    recent = DefendMemory(lane="left", at=60.0 - DEFEND_COOLDOWN_S / 2, threat=100)
    d = decide(state(elixir=5, enemy_our=(100, 0), elapsed=60.0), CHEAP_HAND, None, last_defend=recent)
    assert d.kind != "defend"
    grown = decide(state(elixir=5, enemy_our=(260, 0), elapsed=60.0), CHEAP_HAND, None, last_defend=recent)
    assert grown.kind == "defend"
    later = decide(
        state(elixir=5, enemy_our=(100, 0), elapsed=60.0 + DEFEND_COOLDOWN_S), CHEAP_HAND, None, last_defend=recent
    )
    assert later.kind == "defend"


def test_cheap_role_comes_from_a_known_low_cost_card_set() -> None:
    from pyclashbot.bot.battle_policy import role_for_card

    assert role_for_card("electro_spirit", "spirit") == "cheap"
    assert role_for_card("bats", "back_support") == "cheap"
    assert role_for_card("skeletons", "back_support") == "cheap"
    assert role_for_card("witch", "king_lane") == "support"
    assert role_for_card("pekka", "bridge_line") == "tank"


def state_at_tower(elixir: int, at_tower: tuple[int, int], our_half: tuple[int, int]) -> BattleState:
    return BattleState(elixir, our_half, (0, 0), (0, 0), dict(FULL), 60.0, enemy_at_tower=at_tower)


def test_a_unit_on_our_tower_is_never_trivial() -> None:
    d = decide(state_at_tower(5, at_tower=(14, 0), our_half=(14, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and d.lane == "left"
    assert "support" in d.roles and "building" in d.roles


def test_a_small_group_at_the_bridge_only_gets_a_cheap_answer() -> None:
    d = decide(state_at_tower(5, at_tower=(0, 0), our_half=(50, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and d.roles == ("cheap",)


def test_a_large_group_on_our_tower_unlocks_everything() -> None:
    d = decide(state_at_tower(5, at_tower=(200, 0), our_half=(200, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and "tank" in d.roles and "small_spell" in d.roles


def test_no_chip_during_the_opening() -> None:
    """2026-09-16 matches 4 and 6: an opening Goblin Barrel left 4 elixir when the Hog push came."""
    hand = [HandCard(0, "goblin_barrel", "chip"), HandCard(1, "musketeer", "support")]
    d = decide(state(elixir=10, elapsed=OPENING_S - 1), hand, None)
    assert d.kind != "chip"
    d = decide(state(elixir=CHIP_MIN_ELIXIR, elapsed=OPENING_S + 1), hand, None)
    assert d.kind == "chip"


def state_incoming(elixir: int, incoming: tuple[int, int]) -> BattleState:
    return BattleState(elixir, (0, 0), (0, 0), (0, 0), dict(FULL), 60.0, enemy_incoming=incoming)


def test_incoming_group_is_defended_before_it_crosses() -> None:
    d = decide(state_incoming(6, incoming=(240, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and d.lane == "left"
    assert "support" in d.roles


def test_small_incoming_activity_is_ignored() -> None:
    d = decide(state_incoming(6, incoming=(30, 0)), CHEAP_HAND, None)
    assert d.kind != "defend"


def test_defend_decision_carries_the_threat_it_answered() -> None:
    """2026-09-16 match 25: the cooldown memory stored the raw count (~40) while the decision
    used the floored threat (80), so 'threat doubled' was always true and the bot re-defended."""
    d = decide(state_at_tower(5, at_tower=(40, 0), our_half=(40, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and d.threat == 80
    memory = DefendMemory(lane="left", at=60.0 - 2.0, threat=d.threat)
    again = decide(state_at_tower(5, at_tower=(40, 0), our_half=(40, 0)), CHEAP_HAND, None, last_defend=memory)
    assert again.kind == "hold"


def test_incoming_group_only_triggers_on_arrival() -> None:
    """A group parked on their side of the bridge is not crossing; answer it once, when it appears."""
    d = decide(state_incoming(6, incoming=(240, 0)), CHEAP_HAND, None, incoming_edge=(False, False))
    assert d.kind != "defend"
    d = decide(state_incoming(6, incoming=(240, 0)), CHEAP_HAND, None, incoming_edge=(True, False))
    assert d.kind == "defend"


def test_large_threat_is_not_answered_with_a_cheap_card() -> None:
    """2026-09-16 matches 27/28: Electro Spirits thrown into 260-390 px pushes were pure waste;
    better to hold a few seconds for Witch, Ice Wizard or PEKKA."""
    d = decide(state(elixir=2, enemy_our=(THREAT_LARGE + 100, 0)), CHEAP_HAND, None)
    assert d.kind == "defend" and "cheap" not in d.roles
    only_cheap = [HandCard(0, "electro_spirit", "cheap")]
    assert choose_slot(only_cheap, d.roles, recent=[]) is None
