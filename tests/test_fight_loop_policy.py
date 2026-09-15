"""_fight_loop with the policy: read state, decide, tap the chosen slot at the zone."""

from __future__ import annotations

import pytest

from pyclashbot.bot import fight
from pyclashbot.bot.battle_policy import Decision, HandCard
from pyclashbot.bot.battle_state import BattleState
from pyclashbot.bot.coords import HAND_CARDS_COORDS
from pyclashbot.utils.logger import Logger

FULL = {"our_L": 1.0, "our_R": 1.0, "their_L": 1.0, "their_R": 1.0}


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        self.now += 0.5
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class _FakeEmulator:
    def __init__(self) -> None:
        self.clicks: list[tuple[int, int]] = []

    def click(self, x_coord: int, y_coord: int, clicks: int = 1, interval: float = 0.0) -> None:
        self.clicks.append((x_coord, y_coord))

    def screenshot(self):
        return "frame"  # readers are stubbed; the loop only passes it through


class _FixedRandom:
    @staticmethod
    def randint(_a: int, _b: int) -> int:
        return 0


@pytest.fixture
def world(monkeypatch):
    emulator, logger = _FakeEmulator(), Logger(timed=False)
    ticks = {"n": 0}
    monkeypatch.setattr(fight, "time", _FakeTime())
    monkeypatch.setattr(fight, "create_default_bridge_iar", lambda _e: None)
    monkeypatch.setattr(fight, "_maybe_start_fight_recording", lambda *a, **k: None)
    monkeypatch.setattr(fight, "stop_fight_capture", lambda: None)
    monkeypatch.setattr(fight, "is_hero_champion_ability_visible", lambda _e: False)
    monkeypatch.setattr(fight, "send_emote", lambda *_a: None)
    monkeypatch.setattr(fight, "random", _FixedRandom())

    def in_battle(_e):
        ticks["n"] += 1
        return ticks["n"] <= 6  # six ticks of battle, then it ends

    monkeypatch.setattr(fight, "check_for_in_battle_with_delay", in_battle)
    monkeypatch.setattr(fight, "check_if_battle_has_ended", lambda _e: ticks["n"] > 6)
    monkeypatch.setattr(
        fight, "read_hand", lambda _e: [HandCard(0, "knight", "tank"), HandCard(1, "musketeer", "support")]
    )
    return {"emulator": emulator, "logger": logger, "monkeypatch": monkeypatch}


def _state(elixir: int, enemy_our=(0, 0)) -> BattleState:
    return BattleState(elixir, enemy_our, (0, 0), (0, 0), dict(FULL), 30.0)


def test_attack_taps_the_tank_slot_then_a_bridge_coordinate(world) -> None:
    world["monkeypatch"].setattr(fight, "read_battle_state", lambda _iar, _t: _state(9))
    world["monkeypatch"].setattr(fight, "zone_play_coords", lambda zone, lane, group: (113, 286))

    assert fight._fight_loop(world["emulator"], world["logger"], False) is True

    clicks = world["emulator"].clicks
    assert clicks[0] == HAND_CARDS_COORDS[0]  # knight is the tank
    assert clicks[1] == (113, 286)


def test_hold_makes_no_taps(world) -> None:
    world["monkeypatch"].setattr(fight, "read_battle_state", lambda _iar, _t: _state(3))

    assert fight._fight_loop(world["emulator"], world["logger"], False) is True
    assert world["emulator"].clicks == []


def test_defend_plays_support_when_no_building_in_hand(world) -> None:
    world["monkeypatch"].setattr(fight, "read_battle_state", lambda _iar, _t: _state(2, enemy_our=(0, 90)))
    seen = {}

    def zone(zone_name, lane, group):
        seen.update(zone=zone_name, lane=lane, group=group)
        return (295, 340)

    world["monkeypatch"].setattr(fight, "zone_play_coords", zone)

    fight._fight_loop(world["emulator"], world["logger"], False)

    assert seen == {"zone": "defense", "lane": "right", "group": "back_support"}
    assert world["emulator"].clicks[0] == HAND_CARDS_COORDS[1]  # musketeer, not the tank


def test_play_decision_returns_none_when_no_card_fits(world) -> None:
    decision = Decision("attack", "left", ("building",), 8, "bridge", "test")
    hand = [HandCard(0, "knight", "tank")]
    assert fight.play_decision(world["emulator"], world["logger"], decision, hand, 10.0, False, []) is None
    assert world["emulator"].clicks == []
