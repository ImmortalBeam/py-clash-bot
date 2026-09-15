"""random module for randomizing fight plays"""

import random
import time
from typing import Literal

from pyclashbot.bot.battle_policy import (
    Decision,
    HandCard,
    PushMemory,
    attack_lane,
    choose_slot,
    decide,
    role_for_group,
)
from pyclashbot.bot.battle_state import read_battle_state
from pyclashbot.bot.card_detection import (
    check_which_cards_are_available,
    create_default_bridge_iar,
    get_card_group,
    identify_hand_cards,
    is_hero_champion_ability_visible,
    switch_side,
    trigger_hero_champion_ability,
    zone_play_coords,
)
from pyclashbot.bot.coords import (
    CLOSE_BATTLE_LOG_BUTTON,
    EMOTE_BUTTON_COORD,
    EMOTE_ICON_COORDS,
    HAND_CARDS_COORDS,
    PLAYABLE_PLAY_REGION_LTRB,
    QUICKMATCH_POPUP_BUTTON_COORD,
    START_FIGHT_BUTTON_COORD,
)
from pyclashbot.bot.find import find_play_again_button
from pyclashbot.bot.nav import (
    check_for_in_battle_with_delay,
    get_to_activity_log,
    get_to_main_after_fight,
    handle_reward_choice,
    handle_trophy_reward_menu,
    wait_for_battle_start,
    wait_for_clash_main_menu,
)
from pyclashbot.bot.recorder import (
    finish_fight_recording,
    is_recording,
    log_play,
    start_fight_recording,
    stop_fight_capture,
)
from pyclashbot.bot.state_detect import (
    check_for_reward_choice_screen,
    check_for_trophy_reward_menu,
    check_if_battle_has_ended,
    check_if_on_clash_main_menu,
    check_if_result_screen_is_victory,
    check_pixels_for_win_in_battle_log,
    count_elixir,
)
from pyclashbot.utils.logger import Logger
from pyclashbot.utils.versioning import __version__

ELIXIR_WAIT_TIMEOUT = 40  # too high but someone got errors with that so idk
ABILITY_TRIGGER_DELAY_S = 3
POLICY_TICK_S = 0.5  # how often the policy re-reads the screen while holding
HOLD_TIMEOUT_S = 40.0  # give up holding (assume the elixir bar is unreadable) and play anyway
DETECTION_LOST_LIMIT = 4


def _maybe_start_fight_recording(
    emulator, logger, recording_flag: bool, fight_mode_chosen: str, custom_path: str | None = None
) -> None:
    """Begin opt-in training-data capture for 1v1-type fights only (Trophy Road / Classic 1v1, never 2v2)."""
    if recording_flag and fight_mode_chosen in ["Classic 1v1", "Trophy Road"]:
        pack_mode = "1v1_trophy" if fight_mode_chosen == "Trophy Road" else "1v1_classic"
        start_fight_recording(emulator, pack_mode, __version__, logger=logger, custom_path=custom_path)


def do_fight_state(
    emulator,
    logger: Logger,
    random_fight_mode,
    fight_mode_chosen,
    called_from_launching=False,
    recording_flag: bool = False,
    custom_path: str | None = None,
) -> bool:
    """Handle the entirety of a battle state (start fight, do fight, end fight)."""

    logger.change_status("Waiting for battle to start")

    # Wait for battle start
    if wait_for_battle_start(emulator, logger) is False:
        logger.change_status("Timed out waiting for battle to start")
        return False

    logger.change_status("Starting fight loop")
    logger.log(f'This is the fight mode: "{fight_mode_chosen}"')

    # Recording is started/stopped inside the fight loops themselves so each pack
    # brackets exactly the in-battle play loop (no pre-battle wait or post-fight nav).
    # Run regular fight loop if random mode not toggled
    if not random_fight_mode and _fight_loop(emulator, logger, recording_flag, fight_mode_chosen, custom_path) is False:
        logger.change_status("Fight loop failed")
        return False

    # Run random fight loop if random mode toggled
    if (
        random_fight_mode
        and _random_fight_loop(emulator, logger, recording_flag, fight_mode_chosen, custom_path) is False
    ):
        logger.change_status("Fight loop failed")
        return False

    # Only log the fight if not called from the start
    if not called_from_launching:
        if fight_mode_chosen in ["Classic 1v1", "Trophy Road"]:
            logger.add_1v1_fight()
        elif fight_mode_chosen == "Classic 2v2":
            logger.increment_2v2_fights()

        if fight_mode_chosen == "Trophy Road":
            logger.increment_trophy_road_fights()
        elif fight_mode_chosen == "Classic 1v1":
            logger.increment_classic_1v1_fights()
        elif fight_mode_chosen == "Classic 2v2":
            logger.increment_classic_2v2_fights()

    time.sleep(10)
    return True


def start_fight(emulator, logger, mode) -> bool:
    """Start a fight with the specified mode.

    Args:
        emulator: The emulator controller
        logger: Logger instance
        mode: Fight mode - must be one of "Classic 1v1", "Classic 2v2", or "Trophy Road"

    Returns:
        bool: True if fight started successfully, False otherwise
    """
    # Validate mode parameter
    logger.log(f'Input mode type: "{type(mode)}"')
    logger.log(f"Input mode value: {mode}")
    valid_modes = ["Classic 1v1", "Classic 2v2", "Trophy Road"]
    logger.log(f"Valid modes: {valid_modes}")
    if mode not in valid_modes:
        logger.log(f"The valid modes for start_fight() are: {valid_modes}")
        logger.log(f"But start_fight() got an invalid mode: '{mode}'")
        return False

    logger.change_status(f"Starting a {mode} fight")

    # Check if on clash main menu
    logger.log("Checking if on main menu before starting fight...")
    if not check_if_on_clash_main_menu(emulator):
        logger.change_status("Not on main menu — cannot start fight")
        return False

    # For all modes (1v1 and 2v2), use the same start button
    # Mode is already set by select_mode() in states.py, just click start button
    emulator.click(START_FIGHT_BUTTON_COORD[0], START_FIGHT_BUTTON_COORD[1])
    logger.log(f"Clicked Start button at {START_FIGHT_BUTTON_COORD}")

    # 2v2 needs a second popup after Start
    if mode == "Classic 2v2":
        logger.change_status("Classic 2v2 — clicking Quick Match popup...")
        time.sleep(3)
        emulator.click(QUICKMATCH_POPUP_BUTTON_COORD[0], QUICKMATCH_POPUP_BUTTON_COORD[1])
        logger.log(f"Clicked Quickmatch button at {QUICKMATCH_POPUP_BUTTON_COORD}")

    return True


def send_emote(emulator, logger: Logger):
    """Method to do an emote in a fight"""
    logger.change_status("Sending emote")

    # click emote button
    emulator.click(EMOTE_BUTTON_COORD[0], EMOTE_BUTTON_COORD[1])
    time.sleep(0.33)

    emote_coord = random.choice(EMOTE_ICON_COORDS)
    emulator.click(emote_coord[0], emote_coord[1])


RANDOM_PLAY_ELIXIR_MIN = 3
RANDOM_PLAY_ELIXIR_MAX = 9


def play_random_available_card(emulator, logger, recording_flag: bool, elapsed_s: float) -> bool:
    """Play one card that is actually available, at a random friendly-half coord.

    Mirrors the rl-bot RandomPlayer so recorded plays are never polluted with cards
    that didn't deploy: read the available hand slots (affordable, non-empty) and, if
    any, play a random one; if none are available, do nothing. Returns True if a card
    was played. The caller gates this behind a random elixir wait.
    """
    card_indices = check_which_cards_are_available(emulator, check_side=True)
    if not card_indices:
        return False  # nothing playable -> no play, nothing recorded (caller re-rolls)

    card_index = random.choice(card_indices)
    left, top, right, bottom = PLAYABLE_PLAY_REGION_LTRB
    play_coord = (random.randint(left, right), random.randint(top, bottom))

    emulator.click(HAND_CARDS_COORDS[card_index][0], HAND_CARDS_COORDS[card_index][1])
    time.sleep(0.1)
    emulator.click(play_coord[0], play_coord[1])
    time.sleep(0.1)

    if recording_flag:
        # Card identity isn't computed for random plays; home re-derives it from pixels.
        log_play(card_index, play_coord[0], play_coord[1], elapsed_s)
    logger.add_card_played()
    return True


def wait_for_elixir(
    emulator,
    logger,
    elixir_wait_amount,
    WAIT_THRESHOLD=5000,  # noqa: N803
    PLAY_THRESHOLD=10000,  # noqa: N803
    recording_flag: bool = False,
) -> Literal["restart", "no battle"] | bool:
    """Method to wait for 4 elixir during a battle"""
    start_time = time.time()
    battle_detection_lost_count = 0
    last_logged_second = -1
    last_lost_detection_log_second = -1
    ability_available_since = None

    while not count_elixir(emulator, elixir_wait_amount):
        # debug screenshot saving removed from production
        wait_time = time.time() - start_time
        elapsed_second = int(wait_time)
        if elapsed_second != last_logged_second:
            logger.change_status(
                f"Waiting for {elixir_wait_amount} elixir for {elapsed_second}s...",
            )
            last_logged_second = elapsed_second

        card_indices = check_which_cards_are_available(emulator)
        if is_hero_champion_ability_visible(emulator):
            if ability_available_since is None:
                ability_available_since = time.time()
                logger.change_status(
                    f"Hero/Champion ability ready — triggering in {ABILITY_TRIGGER_DELAY_S}s",
                )
            elif time.time() - ability_available_since >= ABILITY_TRIGGER_DELAY_S:
                trigger_hero_champion_ability(emulator, logger)
                ability_available_since = None
        else:
            ability_available_since = None

        card_inhand = len(card_indices)
        action_offset, _ = switch_side()
        if action_offset > PLAY_THRESHOLD and card_inhand > 0:
            logger.change_status("Battle too active — playing now")
            return True

        if action_offset > WAIT_THRESHOLD and card_inhand == 4:
            logger.change_status("All cards are available!")
            return True

        if wait_time > ELIXIR_WAIT_TIMEOUT:
            logger.change_status(status="Waited too long for elixir")
            return "restart"

        if not check_for_in_battle_with_delay(emulator):
            if check_if_battle_has_ended(emulator):
                logger.change_status(status="Battle ended — stopping elixir wait")
                return "no battle"

            battle_detection_lost_count += 1
            lost_detection_second = int(time.time())
            if lost_detection_second != last_lost_detection_log_second:
                logger.change_status(
                    status="Lost battle detection while waiting for elixir — assuming still in battle",
                )
                last_lost_detection_log_second = lost_detection_second
            if battle_detection_lost_count >= 4:
                logger.change_status(
                    status="Lost battle detection repeatedly — assuming battle ended",
                )
                return "no battle"

            time.sleep(0.5)
            continue

        battle_detection_lost_count = 0

    logger.change_status(
        f"Took {str(time.time() - start_time)[:4]}s for {elixir_wait_amount} elixir.",
    )

    return True


# Result-screen Play Again: how long to look for the button before giving up and
# taking the normal OK path, and how long to wait for the next battle to begin.
PLAY_AGAIN_FIND_TIMEOUT_S = 10.0
PLAY_AGAIN_POLL_INTERVAL_S = 0.5
PLAY_AGAIN_BATTLE_START_TIMEOUT_S = 60


def _apply_fight_outcome(logger: Logger, is_win: bool | None, disable_win_tracker_toggle: bool) -> None:
    """Record a fight's outcome: win/loss stats (only when the tracker is on and the
    result is known) and the recording manifest (always closed; no-op when idle)."""
    if is_win is None:
        outcome = None
        logger.log("Fight outcome unknown — not counted")
    else:
        outcome = "win" if is_win else "loss"
        logger.change_status(f"Last game result: {outcome}")
        if not disable_win_tracker_toggle:
            if is_win:
                logger.add_win()
            else:
                logger.add_loss()

    finish_fight_recording(outcome)


def play_again_state(
    emulator,
    logger: Logger,
    disable_win_tracker_toggle: bool = True,
) -> Literal["next_fight", "main_menu", "end_fight", "restart"]:
    """On the 1v1 result screen, record the outcome and press Play Again.

    Returns:
        "next_fight": Play Again pressed and the next battle started (outcome recorded).
        "main_menu": Play Again pressed but no battle came; recovered to the main menu
            (outcome recorded — the caller must skip end_fight's own win check).
        "end_fight": Play Again never appeared (or the game is already on the main
            menu); nothing was recorded — take the normal OK path.
        "restart": recovery to the main menu failed.
    """
    logger.change_status("Looking for Play Again on the result screen")
    deadline = time.time() + PLAY_AGAIN_FIND_TIMEOUT_S
    button_coord = None
    while time.time() < deadline:
        if check_if_on_clash_main_menu(emulator):
            logger.log("Already on main menu — no Play Again to press")
            return "end_fight"

        if check_for_trophy_reward_menu(emulator):
            handle_trophy_reward_menu(emulator, logger, printmode=True)
            time.sleep(2)
            continue

        if check_for_reward_choice_screen(emulator):
            handle_reward_choice(emulator, logger)
            time.sleep(2)
            continue

        button_coord = find_play_again_button(emulator)
        if button_coord is not None:
            break

        time.sleep(PLAY_AGAIN_POLL_INTERVAL_S)

    if button_coord is None:
        logger.log("Play Again button not found — falling back to the OK path")
        return "end_fight"

    # Read the result off this screen before it goes away. Force it while recording so
    # the pack gets a real outcome; otherwise honor the user's win-tracker toggle.
    is_win: bool | None = None
    if is_recording() or not disable_win_tracker_toggle:
        is_win = check_if_result_screen_is_victory(emulator)
    _apply_fight_outcome(logger, is_win, disable_win_tracker_toggle)

    logger.change_status("Pressing Play Again")
    emulator.click(button_coord[0], button_coord[1])

    if wait_for_battle_start(emulator, logger, timeout=PLAY_AGAIN_BATTLE_START_TIMEOUT_S):
        return "next_fight"

    logger.change_status("No battle after Play Again — returning to main menu")
    if get_to_main_after_fight(emulator, logger) is False:
        logger.log("Failed to return to main menu after Play Again")
        return "restart"
    return "main_menu"


def end_fight_state(
    emulator,
    logger: Logger,
    recording_flag,
    disable_win_tracker_toggle=True,
):
    """Method to handle the time after a fight and before the next state"""
    # count the crown score on this end-battle screen

    # get to clash main after this fight
    logger.log("Returning to main menu after fight")
    if get_to_main_after_fight(emulator, logger) is False:
        logger.log("Failed to return to main menu after fight")
        finish_fight_recording(None)
        return False

    logger.log("Returned to main menu after fight")
    time.sleep(3)

    # Determine the outcome. Force the win check when a recording is active so the
    # pack gets a real win/loss; otherwise honor the user's win-tracker toggle.
    if is_recording() or not disable_win_tracker_toggle:
        win_check_return = check_if_previous_game_was_win(emulator, logger)

        if win_check_return == "restart":
            logger.log("Failed while checking if previous game was a win")
            finish_fight_recording(None)
            return False

        _apply_fight_outcome(logger, win_check_return, disable_win_tracker_toggle)
    else:
        logger.log("Not checking win/loss because check is disabled")
        finish_fight_recording(None)

    return True


def check_if_previous_game_was_win(
    emulator,
    logger: Logger,
) -> bool | Literal["restart"]:
    """Method to handle the checking if the previous game was a win or loss"""
    logger.change_status(status="Checking last game result")

    # Use wait_for_clash_main_menu to ensure we are on the main menu.
    if not wait_for_clash_main_menu(emulator, logger, deadspace_click=True):
        logger.change_status(status="Not on main menu — cannot check last game result")
        return "restart"

    # get to clash main options menu
    if get_to_activity_log(emulator, logger, printmode=False) == "restart":
        logger.change_status(status="Failed to open battle log")

        return "restart"

    logger.change_status(status="Checking battle log for win...")
    is_a_win = check_pixels_for_win_in_battle_log(emulator)
    result = "win" if is_a_win else "loss"
    logger.change_status(status=f"Last game result: {result}")

    # close battle log
    logger.change_status(status="Returning to main menu")
    emulator.click(CLOSE_BATTLE_LOG_BUTTON[0], CLOSE_BATTLE_LOG_BUTTON[1])
    if wait_for_clash_main_menu(emulator, logger) is False:
        logger.change_status(status="Timed out returning to main menu after battle log")
        return "restart"
    time.sleep(2)

    return is_a_win


# main fight loops


def read_hand(emulator) -> list[HandCard]:
    """Affordable hand slots with their identified card and policy role."""
    hand: list[HandCard] = []
    for slot in check_which_cards_are_available(emulator):
        card_id = identify_hand_cards(emulator, slot) or "unknown"
        hand.append(HandCard(slot, card_id, role_for_group(get_card_group(card_id))))
    return hand


def play_decision(
    emulator,
    logger: Logger,
    decision: Decision,
    hand: list[HandCard],
    elapsed: float,
    recording_flag: bool,
    recent: list[int],
) -> HandCard | None:
    """Tap the first hand card matching the decision's roles at the decision's zone."""
    card = choose_slot(hand, decision.roles, recent)
    if card is None or decision.lane is None:
        return None
    coord = zone_play_coords(decision.zone, decision.lane, get_card_group(card.card_id))
    if coord is None:
        return None
    emulator.click(HAND_CARDS_COORDS[card.slot][0], HAND_CARDS_COORDS[card.slot][1])
    emulator.click(coord[0], coord[1])
    logger.change_status(f"{decision.kind} {decision.lane}: {card.card_id} at {coord} ({decision.reason})")
    logger.add_card_played()
    if recording_flag:
        log_play(card.slot, coord[0], coord[1], elapsed)
    recent.append(card.slot)
    del recent[:-3]
    if random.randint(0, 9) == 1:
        send_emote(emulator, logger)
    return card


def _fight_loop(
    emulator, logger: Logger, recording_flag: bool, fight_mode: str = "Classic 1v1", custom_path: str | None = None
) -> bool:
    """Read the battle, decide, act — until the battle ends."""
    create_default_bridge_iar(emulator)
    _maybe_start_fight_recording(emulator, logger, recording_flag, fight_mode, custom_path)
    prev_cards_played = logger.get_cards_played()
    battle_detection_lost_count = 0
    start_time = time.time()
    hold_since = start_time
    push: PushMemory | None = None
    recent: list[int] = []
    ability_available_since: float | None = None

    while True:
        if not check_for_in_battle_with_delay(emulator):
            if check_if_battle_has_ended(emulator):
                break
            battle_detection_lost_count += 1
            logger.change_status(f"Lost battle detection mid-fight ({battle_detection_lost_count}) — waiting it out")
            if battle_detection_lost_count >= DETECTION_LOST_LIMIT:
                logger.change_status("Lost battle detection repeatedly — assuming battle ended")
                break
            time.sleep(1)
            continue
        battle_detection_lost_count = 0

        elapsed = time.time() - start_time
        iar = emulator.screenshot()
        state = read_battle_state(iar, elapsed)

        if is_hero_champion_ability_visible(emulator):
            if ability_available_since is None:
                ability_available_since = time.time()
            elif time.time() - ability_available_since >= ABILITY_TRIGGER_DELAY_S:
                trigger_hero_champion_ability(emulator, logger)
                ability_available_since = None
        else:
            ability_available_since = None

        hand = read_hand(emulator)
        decision = decide(state, hand, push)

        if decision.kind == "hold":
            if time.time() - hold_since > HOLD_TIMEOUT_S and hand:
                logger.change_status("Held too long — playing the first affordable card")
                decision = Decision(
                    "attack",
                    attack_lane(state),
                    tuple(card.role for card in hand),
                    0,
                    "bridge",
                    "hold timeout",
                )
            else:
                logger.change_status(f"Holding ({decision.reason}), elixir {state.elixir}")
                time.sleep(POLICY_TICK_S)
                continue

        played = play_decision(emulator, logger, decision, hand, elapsed, recording_flag, recent)
        hold_since = time.time()
        if played is None:
            time.sleep(POLICY_TICK_S)
            continue
        if decision.kind == "attack" and played.role in ("tank", "win_condition"):
            push = PushMemory(decision.lane or "left", elapsed)
        elif decision.kind in ("follow_up", "defend"):
            push = None
        time.sleep(1.0)

    # Fight over: freeze capture so the pack excludes post-fight nav (manifest/outcome written later).
    stop_fight_capture()
    logger.change_status("Fight complete")
    time.sleep(2.13)
    cards_played = logger.get_cards_played()
    logger.change_status(f"Played ~{cards_played - prev_cards_played} cards this fight")

    return True


def _random_fight_loop(
    emulator,
    logger,
    recording_flag: bool = False,
    fight_mode_chosen: str = "Trophy Road",
    custom_path: str | None = None,
) -> bool:
    """Method for handling dynamically timed fight with random plays"""
    logger.change_status(status="Starting battle with random plays")
    _maybe_start_fight_recording(emulator, logger, recording_flag, fight_mode_chosen, custom_path)
    create_default_bridge_iar(emulator)
    fight_timeout = 5 * 60  # 5 minutes
    start_time = time.time()
    battle_detection_lost_count = 0

    # while in battle:
    while True:
        if not check_for_in_battle_with_delay(emulator):
            if check_if_battle_has_ended(emulator):
                break

            battle_detection_lost_count += 1
            logger.change_status(
                f"Lost battle detection mid-fight ({battle_detection_lost_count}) — waiting it out",
            )

            if battle_detection_lost_count >= 4:
                logger.change_status(
                    "Lost battle detection repeatedly — assuming battle ended",
                )
                break

            time.sleep(1)
            continue

        battle_detection_lost_count = 0
        if time.time() - start_time > fight_timeout:
            logger.change_status("Random fight loop timed out after 5 minutes")
            return False

        # Clean random-play flow (mirrors rl-bot RandomPlayer): wait for a random
        # elixir gate, then play only if a card is actually available.
        target = random.randint(RANDOM_PLAY_ELIXIR_MIN, RANDOM_PLAY_ELIXIR_MAX)
        elixir_result = wait_for_elixir(emulator, logger, target, recording_flag=recording_flag)
        if elixir_result == "no battle":
            break
        if elixir_result == "restart":
            return False
        play_random_available_card(emulator, logger, recording_flag, time.time() - start_time)

    # Fight over: freeze capture so the pack excludes post-fight nav (manifest/outcome written later).
    stop_fight_capture()
    logger.change_status("Random-plays fight complete")
    return True


if __name__ == "__main__":
    pass
