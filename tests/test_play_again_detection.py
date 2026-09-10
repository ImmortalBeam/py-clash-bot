"""Post-battle result screen: Play Again button and Victory/Defeat detection.

Fixtures are real 419x633 emulator screenshots (BGR) with player names masked.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pyclashbot.bot.coords import PLAY_AGAIN_BUTTON_COORD
from pyclashbot.bot.find import find_play_again_button, find_post_battle_button
from pyclashbot.bot.state_detect import check_for_play_again_button, check_if_result_screen_is_victory

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
VICTORY = FIXTURES / "result_screen_victory.png"
MAIN_MENU = FIXTURES / "main_menu_left_column_icons.png"


class _BgrEmulator:
    def __init__(self, bgr: np.ndarray) -> None:
        self._bgr = bgr

    def screenshot(self) -> np.ndarray:
        return self._bgr


def _load(path: Path) -> _BgrEmulator:
    if not path.is_file():
        raise AssertionError(f"missing fixture: {path}")
    rgb = np.array(Image.open(path).convert("RGB"))
    return _BgrEmulator(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def test_play_again_button_found_on_result_screen() -> None:
    coord = find_play_again_button(_load(VICTORY))
    assert coord is not None
    assert _distance(coord, PLAY_AGAIN_BUTTON_COORD) <= 15


def test_play_again_button_absent_on_main_menu() -> None:
    assert find_play_again_button(_load(MAIN_MENU)) is None
    assert check_for_play_again_button(_load(MAIN_MENU)) is False


def test_play_again_button_predicate_on_result_screen() -> None:
    assert check_for_play_again_button(_load(VICTORY)) is True


def test_ok_button_still_found_and_distinct_from_play_again() -> None:
    ok = find_post_battle_button(_load(VICTORY))
    assert ok is not None
    assert _distance(ok, PLAY_AGAIN_BUTTON_COORD) >= 40


def test_victory_detected_on_winning_result_screen() -> None:
    assert check_if_result_screen_is_victory(_load(VICTORY)) is True


def test_result_unknown_on_main_menu() -> None:
    assert check_if_result_screen_is_victory(_load(MAIN_MENU)) is None


def test_play_again_template_fallback_returns_button_centre(monkeypatch) -> None:
    """With the pixel fingerprint disabled, the template path must still land on the button."""
    from pyclashbot.bot import state_detect

    monkeypatch.setattr(state_detect, "_PLAY_AGAIN_BUTTON_PIXELS", ())
    coord = find_play_again_button(_load(VICTORY))
    assert coord is not None
    assert _distance(coord, PLAY_AGAIN_BUTTON_COORD) <= 15
