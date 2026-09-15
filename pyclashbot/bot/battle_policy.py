"""Pure battle decisions: BattleState + hand -> Decision. No screen I/O, no clicks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyclashbot.bot.battle_state import BattleState

FOLLOW_UP_WINDOW_S = 8.0
FINISH_HP = 0.15
ENDGAME_S = 120.0  # double elixir: one less elixir needed to commit
LAST_SECONDS_S = 30.0
MATCH_LENGTH_S = 180.0
CHIP_MIN_ELIXIR = 5

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


def decide(state: BattleState, hand: list[HandCard], push: PushMemory | None) -> Decision:
    mode = game_mode(state)

    lane = state.threatened_lane()
    if lane is not None:
        return Decision(
            "defend", lane, ("building", "support", "tank", "small_spell"), 0, "defense", f"enemy on our {lane}"
        )

    if push is not None and state.elapsed - push.started_at <= FOLLOW_UP_WINDOW_S and _has_role(hand, "support"):
        return Decision("follow_up", push.lane, ("support",), 0, "support_behind", f"support the {push.lane} push")

    for lane_name, key in (("left", "their_L"), ("right", "their_R")):
        hp = state.tower_hp.get(key)
        if hp is not None and hp < FINISH_HP:
            if _has_role(hand, "big_spell"):
                return Decision("finish", lane_name, ("big_spell",), 0, "spell_tower", f"finish {lane_name} tower")
            if _has_role(hand, "chip"):
                return Decision("finish", lane_name, ("chip",), 0, "chip", f"finish {lane_name} tower")

    target = state.weakest_enemy_lane()
    threshold = attack_threshold(mode, state.elapsed)
    if target is not None and state.elixir >= threshold and _has_role(hand, "tank", "win_condition"):
        return Decision(
            "attack", target, ("tank", "win_condition"), threshold, "bridge", f"{mode}: push {target} at {threshold}"
        )

    if target is not None and state.elixir >= CHIP_MIN_ELIXIR and _has_role(hand, "chip"):
        return Decision("chip", target, ("chip",), CHIP_MIN_ELIXIR, "chip", f"chip {target} tower")

    if target is not None and state.elixir >= threshold and _has_role(hand, "support"):
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
