"""Regression: the battle-wait "dead space" tap must not land on a main-menu button.

While waiting for a battle to start the bot taps ``BATTLE_WAIT_DEADSPACE_COORD``
several times a second. If matchmaking is cancelled (or never started) the game is
back on the main menu, and a tap on an interactive element there loops forever:
the old ``(20, 200)`` sat on the daily-gift icon and toggled its popup for the
full wait timeout instead of leaving the menu untouched.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pyclashbot.bot.coords import BATTLE_WAIT_DEADSPACE_COORD
from pyclashbot.bot.state_detect import check_if_on_clash_main_menu

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "main_menu_left_column_icons.png"

# Main-menu tile background is dark blue; buttons/icons are far brighter.
BACKGROUND_MAX_CHANNEL = 130


class _BgrEmulator:
    def __init__(self, bgr: np.ndarray) -> None:
        self._bgr = bgr

    def screenshot(self) -> np.ndarray:
        return self._bgr


def _load_bgr() -> np.ndarray:
    if not FIXTURE.is_file():
        raise AssertionError(f"missing fixture: {FIXTURE}")
    rgb = np.array(Image.open(FIXTURE).convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def test_fixture_is_a_main_menu_screenshot() -> None:
    assert check_if_on_clash_main_menu(_BgrEmulator(_load_bgr()))


def test_battle_wait_deadspace_is_plain_background_on_main_menu() -> None:
    bgr = _load_bgr()
    x, y = BATTLE_WAIT_DEADSPACE_COORD
    pixel = bgr[y][x].tolist()
    assert max(pixel) < BACKGROUND_MAX_CHANNEL, (
        f"BATTLE_WAIT_DEADSPACE_COORD {BATTLE_WAIT_DEADSPACE_COORD} is on a bright UI element "
        f"(BGR {pixel}); pick a spot that is plain background on the main menu"
    )
