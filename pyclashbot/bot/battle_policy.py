"""Pure battle decisions: BattleState + hand -> Decision. No screen I/O, no clicks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyclashbot.bot.battle_state import BattleState

FOLLOW_UP_WINDOW_S = 8.0
FINISH_HP = 0.15
FINISH_MIN_ELAPSED_S = 20.0  # a tower cannot be near death this early; treat low reads as noise
ENDGAME_S = 120.0  # double elixir: one less elixir needed to commit
LAST_SECONDS_S = 30.0
MATCH_LENGTH_S = 180.0
TOWER_UNDER_FIRE_DROP = 0.08  # health lost between two ticks that means something is hitting the tower
CHIP_MIN_ELIXIR = 7  # keep a cushion: a chip card must not leave us empty for the counter-push
PUSH_COOLDOWN_S = 15.0  # no chip on top of a push we just committed to

# PLAY_COORDS group -> role. Unknown groups (and "No group") are support.
ROLE_OF_GROUP: dict[str, str] = {
    "bridge_line": "tank",
    "bridge_rush": "win_condition",
    "back_support": "support",
    "king_lane": "support",
    "princess": "support",
    "spirit": "support",
    "defense_building": "building",
    "siege_building": "building",
    "reactive_spell": "small_spell",
    "lane_spell": "small_spell",
    "center_spell": "small_spell",
    "tornado": "small_spell",
    "large_spell": "big_spell",
    "rocket": "big_spell",
    "goblin_barrel": "chip",
    "graveyard": "chip",
    "miner": "chip",
    "goblin_drill": "chip",
}


def role_for_group(group: str) -> str:
    return ROLE_OF_GROUP.get(group, "support")


@dataclass(frozen=True)
class HandCard:
    slot: int
    card_id: str
    role: str


@dataclass
class PushMemory:
    lane: str
    started_at: float


@dataclass(frozen=True)
class Decision:
    kind: str  # defend | follow_up | finish | attack | chip | hold
    lane: str | None
    roles: tuple[str, ...]
    min_elixir: int
    zone: str  # defense | support_behind | spell_tower | chip | bridge | none
    reason: str


def game_mode(state: BattleState) -> str:
    ours, theirs = state.standing_towers("our"), state.standing_towers("their")
    if ours > theirs:
        return "ahead"
    if ours < theirs:
        return "behind"
    return "even"


def attack_threshold(mode: str, elapsed: float) -> int:
    threshold = {"ahead": 9, "even": 8, "behind": 7}[mode]
    if elapsed >= ENDGAME_S:
        threshold -= 1
    if elapsed >= MATCH_LENGTH_S - LAST_SECONDS_S and mode != "ahead":
        threshold = min(threshold, 5)
    return threshold


def _has_role(hand: list[HandCard], *roles: str) -> bool:
    return any(card.role in roles for card in hand)


def under_fire_lane(prev_hp: dict[str, float | None] | None, hp: dict[str, float | None]) -> str | None:
    """Lane whose princess tower lost a chunk of health since the previous tick.

    Catches attackers with little or no health bar on our half (Balloon, spells).
    """
    if prev_hp is None:
        return None
    worst_lane, worst_drop = None, TOWER_UNDER_FIRE_DROP
    for lane, key in (("left", "our_L"), ("right", "our_R")):
        before, now = prev_hp.get(key), hp.get(key)
        if before is None or now is None:
            continue
        if before - now >= worst_drop:
            worst_lane, worst_drop = lane, before - now
    return worst_lane


def attack_lane(state: BattleState) -> str:
    """Lane to push: the weakest standing enemy princess tower, or, once both are down,
    the king through the lane where our own tower still protects the path."""
    lane = state.weakest_enemy_lane()
    if lane is not None:
        return lane
    return "left" if state.tower_hp.get("our_L") is not None else "right"


def decide(
    state: BattleState, hand: list[HandCard], push: PushMemory | None, under_fire: str | None = None
) -> Decision:
    mode = game_mode(state)

    lane = state.threatened_lane() or under_fire
    if lane is not None:
        why = f"enemy on our {lane}" if state.threatened_lane() else f"our {lane} tower under fire"
        return Decision("defend", lane, ("building", "support", "tank", "small_spell"), 0, "defense", why)

    if push is not None and state.elapsed - push.started_at <= FOLLOW_UP_WINDOW_S and _has_role(hand, "support"):
        return Decision("follow_up", push.lane, ("support",), 0, "support_behind", f"support the {push.lane} push")

    for lane_name, key in (("left", "their_L"), ("right", "their_R")):
        hp = state.tower_hp.get(key)
        if hp is not None and hp < FINISH_HP and state.elapsed >= FINISH_MIN_ELAPSED_S:
            if _has_role(hand, "big_spell"):
                return Decision("finish", lane_name, ("big_spell",), 0, "spell_tower", f"finish {lane_name} tower")
            if _has_role(hand, "chip"):
                return Decision("finish", lane_name, ("chip",), 0, "chip", f"finish {lane_name} tower")

    target = attack_lane(state)
    threshold = attack_threshold(mode, state.elapsed)
    if state.elixir >= threshold and _has_role(hand, "tank", "win_condition"):
        return Decision(
            "attack", target, ("tank", "win_condition"), threshold, "bridge", f"{mode}: push {target} at {threshold}"
        )

    push_settled = push is None or state.elapsed - push.started_at > PUSH_COOLDOWN_S
    if push_settled and state.elixir >= CHIP_MIN_ELIXIR and _has_role(hand, "chip"):
        return Decision("chip", target, ("chip",), CHIP_MIN_ELIXIR, "chip", f"chip {target} tower")

    if state.elixir >= threshold and _has_role(hand, "support"):
        # No tank in hand: lead with support rather than sit on full elixir.
        return Decision("attack", target, ("support",), threshold, "bridge", f"{mode}: support push {target}")

    return Decision("hold", None, (), threshold, "none", f"{mode}: wait for {threshold} elixir")


def choose_slot(hand: list[HandCard], roles: tuple[str, ...], recent: list[int]) -> HandCard | None:
    for role in roles:
        matching = [card for card in hand if card.role == role]
        if not matching:
            continue
        fresh = [card for card in matching if card.slot not in recent]
        return (fresh or matching)[0]
    return None
