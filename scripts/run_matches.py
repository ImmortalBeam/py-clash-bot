"""Play N Trophy Road matches with the bot's own fight code, capture a frame every
few seconds, and write a per-match summary (outcome, duration, frames) for analysis.

Usage: uv run python scripts/run_matches.py <out_dir> [n_matches] [adb_serial]
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import cv2

from pyclashbot.bot.fight import do_fight_state, end_fight_state, play_again_state, start_fight
from pyclashbot.bot.nav import wait_for_clash_main_menu
from pyclashbot.emulators.adb import AdbController
from pyclashbot.utils.logger import Logger, initialize_pylogging

OUT = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
MODE = "Trophy Road"
FRAME_EVERY_S = 4.0
SERIAL = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1:5565"


class FrameGrabber:
    def __init__(self, emulator, folder: str) -> None:
        self.emulator, self.folder = emulator, folder
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.count = 0

    def _run(self) -> None:
        t0 = time.time()
        while not self._stop.is_set():
            try:
                im = self.emulator.screenshot()
                if im is not None:
                    cv2.imwrite(os.path.join(self.folder, f"{int(time.time() - t0):04d}.png"), im)
                    self.count += 1
            except Exception as e:
                print("frame grab failed:", e, flush=True)
            self._stop.wait(FRAME_EVERY_S)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    initialize_pylogging()
    logger = Logger(timed=False)
    emulator = AdbController(logger, SERIAL)
    emulator.restart()
    summary: list[dict[str, object]] = []
    in_battle = False

    for i in range(1, N + 1):
        match_dir = os.path.join(OUT, f"match_{i:02d}")
        os.makedirs(os.path.join(match_dir, "frames"), exist_ok=True)
        rec: dict[str, object] = {"match": i, "start": time.time()}
        wins0, losses0 = logger.wins, logger.losses

        if not in_battle:
            if not wait_for_clash_main_menu(emulator, logger):
                rec["error"] = "no main menu"
                summary.append(rec)
                emulator.restart()
                continue
            if start_fight(emulator, logger, MODE) is False:
                rec["error"] = "start_fight failed"
                summary.append(rec)
                continue

        grabber = FrameGrabber(emulator, os.path.join(match_dir, "frames"))
        grabber.start()
        ok = do_fight_state(emulator, logger, False, MODE, False, recording_flag=False)
        grabber.stop()
        rec["fight_ok"] = bool(ok)
        rec["frames"] = grabber.count
        rec["fight_end"] = time.time()
        result_im = emulator.screenshot()
        if result_im is not None:
            cv2.imwrite(os.path.join(match_dir, "result.png"), result_im)

        if i < N:
            outcome = play_again_state(emulator, logger, disable_win_tracker_toggle=False)
            rec["transition"] = outcome
            in_battle = outcome == "next_fight"
            if outcome == "end_fight":
                end_fight_state(emulator, logger, False, False)
            elif outcome == "restart":
                emulator.restart()
        else:
            end_fight_state(emulator, logger, False, False)
            rec["transition"] = "end_fight(final)"
            in_battle = False

        rec["result"] = "win" if logger.wins > wins0 else ("loss" if logger.losses > losses0 else "unknown")
        rec["end"] = time.time()
        summary.append(rec)
        with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"MATCH {i}: {rec['result']} transition={rec['transition']} frames={rec['frames']}", flush=True)

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
