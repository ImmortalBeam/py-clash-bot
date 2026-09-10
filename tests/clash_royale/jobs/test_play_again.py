"""Test: Play Again chains two 1v1 battles without a main-menu round trip.

Begins on main, starts a 1v1 battle, plays it out, then on the result screen
play_again_state must record the outcome and press Play Again so a second
battle starts straight away. The second battle is finished through the normal
end_fight_state path, ending on main. With the win tracker enabled both fights
must be counted (one from the result screen, one from the battle log).

Precondition: emulator running, signed in to Clash Royale, on the main menu,
with a 1v1 mode selected. Patience: two real matches take several minutes.
"""

from __future__ import annotations

from pyclashbot.bot.fight import do_fight_state, end_fight_state, play_again_state, start_fight
from pyclashbot.bot.nav import wait_for_clash_main_menu

MODE = "Classic 1v1"


def run_test(emulator, logger) -> tuple[bool, str]:
    if not wait_for_clash_main_menu(emulator, logger):
        return (False, "Didn't begin on clash main")

    counted_before = logger.wins + logger.losses

    if start_fight(emulator, logger, MODE) is False:
        return (False, f"Failed during start_fight({MODE!r})")

    if do_fight_state(emulator, logger, False, MODE, False, False) is False:
        return (False, "Failed during the first do_fight_state")

    outcome = play_again_state(emulator, logger, disable_win_tracker_toggle=False)
    if outcome != "next_fight":
        return (False, f"play_again_state returned {outcome!r}, expected 'next_fight'")

    if logger.wins + logger.losses != counted_before + 1:
        return (False, "Result screen outcome was not counted before Play Again")

    if do_fight_state(emulator, logger, False, MODE, False, False) is False:
        return (False, "Failed during the second do_fight_state")

    if end_fight_state(emulator, logger, False, False) is False:
        return (False, "Failed during end_fight_state")

    if logger.wins + logger.losses != counted_before + 2:
        return (False, "Second fight was not counted by end_fight_state")

    if not wait_for_clash_main_menu(emulator, logger):
        return (False, "Didn't end on clash main")

    return (True, "")
