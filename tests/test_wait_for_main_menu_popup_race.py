"""wait_for_clash_main_menu must survive a popup appearing right after the main menu.

On accounts with a collectable Trophy Road reward the rewards page opens a second
or two after the main menu is first visible. The confirmation check used to fail
once and give up, even though the wait loop knows how to dismiss that page.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pyclashbot.bot import nav
from pyclashbot.bot.nav import wait_for_clash_main_menu
from pyclashbot.utils.logger import Logger

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _bgr(name: str) -> np.ndarray:
    rgb = np.array(Image.open(FIXTURES / name).convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


class _PopupEmulator:
    """Shows main, then pops the rewards page over it after the first look; the page
    only goes away when its OK button is tapped."""

    def __init__(self, main: np.ndarray, rewards: np.ndarray, popup_after_looks: int = 1) -> None:
        self._main, self._rewards = main, rewards
        self._popup_after_looks = popup_after_looks
        self._looks = 0
        self._popup_shown = False
        self.on_rewards = False
        self.clicks: list[tuple[int, int]] = []

    def screenshot(self) -> np.ndarray:
        self._looks += 1
        if not self._popup_shown and self._looks > self._popup_after_looks:
            self._popup_shown = True
            self.on_rewards = True
        return self._rewards if self.on_rewards else self._main

    def click(self, x_coord: int, y_coord: int, clicks: int = 1, interval: float = 0.0) -> None:
        self.clicks.append((x_coord, y_coord))
        if self.on_rewards and (x_coord, y_coord) == nav.OK_BUTTON_COORDS_IN_TROPHY_REWARD_PAGE:
            self.on_rewards = False


def test_main_menu_confirmed_after_rewards_page_interrupts(monkeypatch) -> None:
    monkeypatch.setattr(nav.time, "sleep", lambda _s: None)
    emulator = _PopupEmulator(_bgr("main_menu_left_column_icons.png"), _bgr("trophy_road_rewards_page.png"))

    assert wait_for_clash_main_menu(emulator, Logger(timed=False), deadspace_click=False) is True
    assert nav.OK_BUTTON_COORDS_IN_TROPHY_REWARD_PAGE in emulator.clicks
    assert emulator.on_rewards is False


def test_main_menu_wait_still_times_out(monkeypatch) -> None:
    monkeypatch.setattr(nav.time, "sleep", lambda _s: None)
    rewards = _bgr("trophy_road_rewards_page.png")
    emulator = _PopupEmulator(rewards, rewards)  # never shows main

    assert wait_for_clash_main_menu(emulator, Logger(timed=False), deadspace_click=False, timeout=0) is False
