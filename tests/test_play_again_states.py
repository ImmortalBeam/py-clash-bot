"""State machine wiring for the play_again state: budget, streak and transitions.

play_again_state itself is stubbed; these tests cover how states.py routes its
four outcomes and how the consecutive-fight budget is applied and reset.
"""

from __future__ import annotations

import pytest

from pyclashbot.bot import states
from pyclashbot.bot.states import StateHistory, StateOrder, play_again_budget, state_tree
from pyclashbot.interface.enums import UIField
from pyclashbot.utils.logger import Logger


class _NoEmulator:
    """The play_again branch must not touch the emulator when play_again_state is stubbed."""

    def __getattr__(self, name):
        raise AssertionError(f"emulator.{name} should not be used")


def _jobs(*, play_again: bool = True, fights: object = 2) -> dict[str, object]:
    return {
        UIField.CLASSIC_1V1_USER_TOGGLE.value: True,
        UIField.PLAY_AGAIN_USER_TOGGLE.value: play_again,
        UIField.MAX_PLAY_AGAIN_SELECTION.value: fights,
        UIField.DISABLE_WIN_TRACK_TOGGLE.value: True,
    }


def _run(monkeypatch, outcome: str, jobs: dict[str, object], mode: str = "Trophy Road") -> tuple[str, list[int]]:
    calls: list[int] = []

    def fake_play_again_state(_emulator, _logger, disable_win_tracker_toggle=True):
        calls.append(1)
        return outcome

    monkeypatch.setattr(states, "play_again_state", fake_play_again_state)
    monkeypatch.setattr(states, "mode_used_in_1v1", mode)
    logger = Logger(timed=False)
    result = state_tree(_NoEmulator(), logger, "play_again", jobs, StateHistory(logger), StateOrder())
    return result, calls


@pytest.fixture(autouse=True)
def _reset_streak(monkeypatch):
    monkeypatch.setattr(states, "play_again_streak", 0)


def test_play_again_follows_the_fight_states_and_precedes_end_fight() -> None:
    order = StateOrder()
    assert order.next_state("2v2_fight") == "play_again"
    assert order.next_state("play_again") == "end_fight"


@pytest.mark.parametrize(
    ("jobs", "expected"),
    [
        ({}, 0),
        (_jobs(play_again=False, fights=5), 0),
        (_jobs(play_again=True, fights=5), 5),
        (_jobs(play_again=True, fights=0), 0),
        (_jobs(play_again=True, fights="7"), 7),
        (_jobs(play_again=True, fights="lots"), 0),
        (_jobs(play_again=True, fights=None), 0),
    ],
)
def test_play_again_budget(jobs, expected) -> None:
    assert play_again_budget(jobs) == expected


def test_next_fight_jumps_back_to_the_1v1_fight_state(monkeypatch) -> None:
    result, calls = _run(monkeypatch, "next_fight", _jobs(fights=2))

    assert result == "1v1_fight"
    assert calls == [1]
    assert states.play_again_streak == 1


def test_budget_exhausted_takes_the_ok_path_without_pressing(monkeypatch) -> None:
    monkeypatch.setattr(states, "play_again_streak", 2)

    result, calls = _run(monkeypatch, "next_fight", _jobs(fights=2))

    assert result == "end_fight"
    assert calls == []
    assert states.play_again_streak == 0


def test_main_menu_recovery_skips_end_fight(monkeypatch) -> None:
    monkeypatch.setattr(states, "play_again_streak", 1)

    result, _ = _run(monkeypatch, "main_menu", _jobs(fights=5))

    assert result == StateOrder().next_state("end_fight")
    assert states.play_again_streak == 0


def test_end_fight_outcome_continues_to_end_fight(monkeypatch) -> None:
    monkeypatch.setattr(states, "play_again_streak", 1)

    result, _ = _run(monkeypatch, "end_fight", _jobs(fights=5))

    assert result == "end_fight"
    assert states.play_again_streak == 0


def test_restart_outcome_restarts(monkeypatch) -> None:
    result, _ = _run(monkeypatch, "restart", _jobs(fights=5))

    assert result == "restart"
    assert states.play_again_streak == 0


def test_2v2_mode_is_never_played_again(monkeypatch) -> None:
    result, calls = _run(monkeypatch, "next_fight", _jobs(fights=5), mode="Classic 2v2")

    assert result == "end_fight"
    assert calls == []


def test_toggle_off_keeps_todays_behaviour(monkeypatch) -> None:
    monkeypatch.setattr(states, "play_again_streak", 1)

    result, calls = _run(monkeypatch, "next_fight", _jobs(play_again=False, fights=5))

    assert result == "end_fight"
    assert calls == []
    assert states.play_again_streak == 0


def test_select_battle_mode_resets_the_streak(monkeypatch) -> None:
    monkeypatch.setattr(states, "play_again_streak", 3)
    monkeypatch.setattr(states, "check_if_battle_mode_is_selected", lambda _e, _m: True)
    jobs = {UIField.CLASSIC_1V1_USER_TOGGLE.value: True}

    logger = Logger(timed=False)
    result = state_tree(_NoEmulator(), logger, "select_battle_mode", jobs, StateHistory(logger), StateOrder())

    assert result == "randomize_deck"
    assert states.play_again_streak == 0
