"""play_again_state: press Play Again on the 1v1 result screen, record the outcome first.

All screen I/O is stubbed at the fight-module boundary; the tests assert on the
returned transition, the taps issued, the logger win/loss counters and the
recorder outcome handed to finish_fight_recording.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pyclashbot.bot import fight
from pyclashbot.bot.coords import PLAY_AGAIN_BUTTON_COORD
from pyclashbot.utils.logger import Logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class _FakeTime:
    """Deterministic clock: every time() call advances one second; sleep is free."""

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        self.now += 1.0
        return self.now

    def sleep(self, _seconds: float) -> None:
        return None


class _FakeEmulator:
    def __init__(self) -> None:
        self.clicks: list[tuple[int, int]] = []

    def click(self, x_coord: int, y_coord: int, clicks: int = 1, interval: float = 0.0) -> None:
        self.clicks.append((x_coord, y_coord))

    def screenshot(self):  # never used: every detector is stubbed
        raise AssertionError("screenshot() should not be called in these tests")


def _sequence(values: list[object]) -> Callable[..., object]:
    """Stub returning the given values in order, then the last one forever."""
    it: Iterator[object] = iter(values)
    last = values[-1]

    def _stub(*_args, **_kwargs):
        nonlocal last
        try:
            last = next(it)
        except StopIteration:
            pass
        return last

    return _stub


@pytest.fixture
def world(monkeypatch):
    """Default happy path: result screen with Play Again, victory, next battle starts."""
    emulator = _FakeEmulator()
    logger = Logger(timed=False)
    finished: list[str | None] = []

    monkeypatch.setattr(fight, "time", _FakeTime())
    monkeypatch.setattr(fight, "check_if_on_clash_main_menu", lambda _e: False)
    monkeypatch.setattr(fight, "check_for_trophy_reward_menu", lambda _e: False)
    monkeypatch.setattr(fight, "check_for_reward_choice_screen", lambda _e: False)
    monkeypatch.setattr(fight, "find_play_again_button", lambda _e: PLAY_AGAIN_BUTTON_COORD)
    monkeypatch.setattr(fight, "check_if_result_screen_is_victory", lambda _e: True)
    monkeypatch.setattr(fight, "wait_for_battle_start", lambda *_a, **_k: True)
    monkeypatch.setattr(fight, "get_to_main_after_fight", lambda *_a, **_k: True)
    monkeypatch.setattr(fight, "is_recording", lambda: False)
    monkeypatch.setattr(fight, "finish_fight_recording", lambda outcome: finished.append(outcome))

    return {"emulator": emulator, "logger": logger, "finished": finished, "monkeypatch": monkeypatch}


def test_presses_play_again_and_continues_to_next_fight(world) -> None:
    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "next_fight"
    assert world["emulator"].clicks == [PLAY_AGAIN_BUTTON_COORD]


def test_victory_is_counted_before_pressing_play_again(world) -> None:
    fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert (world["logger"].wins, world["logger"].losses) == (1, 0)
    assert world["finished"] == ["win"]


def test_defeat_is_counted_as_a_loss(world) -> None:
    world["monkeypatch"].setattr(fight, "check_if_result_screen_is_victory", lambda _e: False)

    fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert (world["logger"].wins, world["logger"].losses) == (0, 1)
    assert world["finished"] == ["loss"]


def test_unknown_result_is_not_counted(world) -> None:
    world["monkeypatch"].setattr(fight, "check_if_result_screen_is_victory", lambda _e: None)

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "next_fight"
    assert (world["logger"].wins, world["logger"].losses) == (0, 0)
    assert world["finished"] == [None]


def test_disabled_tracker_leaves_counters_untouched(world) -> None:
    calls: list[object] = []
    world["monkeypatch"].setattr(fight, "check_if_result_screen_is_victory", lambda _e: calls.append(1) or True)

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=True)

    assert result == "next_fight"
    assert calls == []
    assert (world["logger"].wins, world["logger"].losses) == (0, 0)
    assert world["finished"] == [None]


def test_recording_forces_outcome_read_but_not_stats(world) -> None:
    world["monkeypatch"].setattr(fight, "is_recording", lambda: True)

    fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=True)

    assert (world["logger"].wins, world["logger"].losses) == (0, 0)
    assert world["finished"] == ["win"]


def test_falls_back_to_end_fight_when_button_never_appears(world) -> None:
    world["monkeypatch"].setattr(fight, "find_play_again_button", lambda _e: None)

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "end_fight"
    assert world["emulator"].clicks == []
    assert (world["logger"].wins, world["logger"].losses) == (0, 0)
    assert world["finished"] == []


def test_falls_back_to_end_fight_when_already_on_main_menu(world) -> None:
    world["monkeypatch"].setattr(fight, "check_if_on_clash_main_menu", lambda _e: True)

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "end_fight"
    assert world["emulator"].clicks == []


def test_dismisses_trophy_reward_popup_then_presses_play_again(world) -> None:
    handled: list[int] = []
    world["monkeypatch"].setattr(fight, "check_for_trophy_reward_menu", _sequence([True, False]))
    world["monkeypatch"].setattr(fight, "handle_trophy_reward_menu", lambda *_a, **_k: handled.append(1))
    world["monkeypatch"].setattr(fight, "find_play_again_button", _sequence([None, PLAY_AGAIN_BUTTON_COORD]))

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "next_fight"
    assert handled == [1]
    assert world["emulator"].clicks == [PLAY_AGAIN_BUTTON_COORD]


def test_dismisses_reward_choice_screen_then_presses_play_again(world) -> None:
    handled: list[int] = []
    world["monkeypatch"].setattr(fight, "check_for_reward_choice_screen", _sequence([True, False]))
    world["monkeypatch"].setattr(fight, "handle_reward_choice", lambda *_a, **_k: handled.append(1))
    world["monkeypatch"].setattr(fight, "find_play_again_button", _sequence([None, PLAY_AGAIN_BUTTON_COORD]))

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "next_fight"
    assert handled == [1]


def test_recovers_to_main_menu_when_next_battle_never_starts(world) -> None:
    world["monkeypatch"].setattr(fight, "wait_for_battle_start", lambda *_a, **_k: False)

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "main_menu"
    assert (world["logger"].wins, world["logger"].losses) == (1, 0)  # outcome already recorded


def test_restart_when_main_menu_recovery_fails(world) -> None:
    world["monkeypatch"].setattr(fight, "wait_for_battle_start", lambda *_a, **_k: False)
    world["monkeypatch"].setattr(fight, "get_to_main_after_fight", lambda *_a, **_k: False)

    result = fight.play_again_state(world["emulator"], world["logger"], disable_win_tracker_toggle=False)

    assert result == "restart"
