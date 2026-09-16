# --- Clash main / global ---
CLASH_MAIN_DEADSPACE_COORD = (35, 500)

# --- Nav ---
CLASH_MAIN_OPTIONS_BURGER_BUTTON = (390, 62)
BATTLE_LOG_BUTTON = (241, 43)
CARD_PAGE_ICON_FROM_CLASH_MAIN = (108, 598)
CARD_PAGE_ICON_FROM_CARD_PAGE = (147, 598)
CARD_PAGE_EXIT_BUTTON_COORDS = (248, 603)
OK_BUTTON_COORDS_IN_TROPHY_REWARD_PAGE = (209, 599)
REWARD_LEFT_CHOICE_COORD = (112, 363)
REWARD_RIGHT_CHOICE_COORD = (318, 375)
DECK_TABS_REGION = (0, 80, 416, 146)
DECKS_PAGE_BUTTON_COORDS = (125, 60)

# --- Fight ---
CLOSE_BATTLE_LOG_BUTTON = (365, 72)
HAND_CARDS_COORDS = [
    (142, 561),
    (210, 563),
    (272, 561),
    (341, 563),
]
CLOSE_THIS_CHALLENGE_PAGE_BUTTON = (27, 22)
QUICKMATCH_BUTTON_COORD = (274, 353)  # coord of the quickmatch button after you click the battle button
EMOTE_BUTTON_COORD = (67, 521)
EMOTE_ICON_COORDS = [
    (124, 419),
    (182, 420),
    (255, 411),
    (312, 423),
    (133, 471),
    (188, 472),
    (243, 469),
    (308, 470),
]

# --- Deck ---
DECK_OPTIONS_BUTTON_COORDS = (53, 106)
RANDOMIZE_DECK_BUTTON_COORDS = (125, 188)
RANDOMIZE_DECK_CONFIRM_BUTTON_COORDS = (280, 390)

# Unified deck-randomization flow (same buttons for Trophy Road / Classic 1v1 / 2v2).
# Randomizing a full deck pops a "replace deck?" confirm dialog; a partial deck does not.
DECK_PAGE_OPTIONS_BUTTON_COORDS = (57, 104)
RANDOMIZE_DECK_BUTTON_COORD = (117, 186)
CONFIRM_RANDOMIZE_DECK_BUTTON_COORD = (252, 388)

# --- Upgrade ---
UPGRADE_POINTS = [
    (53, 263),  # 1
    (140, 263),  # 2
    (225, 263),  # 3
    (312, 263),  # 4
    (52, 403),  # 5
    (139, 402),  # 6
    (225, 402),  # 7
    (311, 402),  # 8
]
FIRST_UPGRADE_BUTTON_COORD = (241, 542)
SECOND_UPGRADE_BUTTON_COORD = (241, 478)
DEADSPACE_COORD = (10, 323)
CLOSE_CARD_PAGE_COORD = (355, 238)
UPGRADE_PIXEL_TOLERANCE = 30
COIN_INSUFFICIENT_COORD = (359, 210)  # close button of gold popup
COIN_INSUFFICIENT_BGR = (49, 53, 254)
UPGRADE_RETURN_TO_MAIN_COORD_1 = (211, 607)
UPGRADE_RETURN_TO_MAIN_COORD_2 = (243, 600)
CARD_PAGE_OK_BUTTON_COORDS = (194, 597)
CHAMPION_UPGRADE_BUTTON_COORD = (236, 542)
PRINCESS_CARD_BUTTON_COORD = (322, 537)
PRINCESS_INFO_BUTTON_COORD_LOCATION_1 = (212, 607)
PRINCESS_UPGRADE_BUTTON_COORD_LOCATION_1 = (337, 309)
PRINCESS_UPGRADE_BUTTON_COORD_LOCATION_2 = (337, 518)
UPGRADE_PRINCESS_BUTTON_2_COORD = (243, 583)
CONFIRM_UPGRADE_PRINCESS_BUTTON_COORD = (225, 501)
PRINCESS_CARD_PAGE_OK_BUTTON_COORD = (209, 608)

# --- Card mastery ---
CARD_MASTERY_RETURN_TO_MAIN_COORD = (243, 600)
CARD_MASTERY_OPTIONS_COORD = (362, 444)
CARD_MASTERY_TAB_COORD = (99, 166)
CARD_MASTERY_COLLECT_COORD = (260, 420)

# --- Misc fight call sites ---
START_FIGHT_BUTTON_COORD = (203, 487)
QUICKMATCH_POPUP_BUTTON_COORD = (280, 350)
MAG_DUMP_CARD_COORDS = [
    (137, 559),
    (206, 559),
    (274, 599),
    (336, 555),
]
# Tapped repeatedly while waiting for matchmaking. Must be plain background on the
# main menu too: (20, 200) sat on the daily-gift icon and toggled its popup forever
# whenever the search was cancelled. Same dead spot as CLASH_MAIN_DEADSPACE_COORD.
BATTLE_WAIT_DEADSPACE_COORD = (35, 500)

# --- Account switch ---
SWITCH_ACCOUNT_BUTTON_COORD = (221, 468)
ACCOUNT_SLOT_CLICK_COORDS: dict[int, tuple[int, int]] = {
    1: (253, 380),
    2: (251, 476),
    3: (252, 572),
}

# --- Bottom nav (tap targets in the y≈600 bar) ---
BOTTOM_NAV_SHOP_TAB_COORD = (30, 600)
BOTTOM_NAV_CARD_TAB_COORD = (100, 600)
BOTTOM_NAV_CARD_TAB_FROM_MAIN_COORD = (100, 606)  # slightly lower y on the main-page card click
BOTTOM_NAV_BATTLE_TAB_COORD = (170, 600)
BOTTOM_NAV_MAIN_TAB_FROM_SHOP_COORD = (240, 600)
BOTTOM_NAV_MAIN_TAB_FROM_CARD_COORD = (250, 600)
BOTTOM_NAV_CLAN_CHAT_TAB_COORD = (280, 600)
BOTTOM_NAV_SOCIAL_TAB_COORD = (310, 600)  # consolidated from 309/310/315 — see PR body
# In-clan-chat: exit deadspace + tap-target for re-opening Social from inside clan chat.
CLAN_CHAT_EXIT_DEADSPACE_COORD = (200, 600)
CLAN_CHAT_TO_SOCIAL_COORD = (219, 605)

# --- Clan voyage ---
# Close button on the clan voyage popup that can block the main menu.
CLAN_VOYAGE_CLOSE_BUTTON_COORDS = [210, 600]

# --- War page ---
# War sits as a tab inside the Social hub (top row, x=210 y=105).
WAR_TAB_FROM_SOCIAL_COORD = (210, 105)
# When leaving war page, the bottom-nav row has shifted positions vs. main —
# tap deadspace first, then the war-page bottom-nav tap target.
WAR_EXIT_DEADSPACE_COORD = (210, 600)
BOTTOM_NAV_MAIN_TAB_FROM_WAR_COORD = (180, 600)
BOTTOM_NAV_CARD_TAB_FROM_WAR_COORD = (110, 600)
BOTTOM_NAV_SHOP_TAB_FROM_WAR_COORD = (35, 600)
BOTTOM_NAV_CLAN_CHAT_TAB_FROM_WAR_COORD = (265, 600)

# Make-war-deck flow: click the empty deck slot, then "Random Deck", then exit.
MAKE_WAR_DECK_1 = (80, 520)
MAKE_WAR_DECK_2 = (165, 520)
MAKE_WAR_DECK_3 = (250, 520)
MAKE_WAR_DECK_4 = (240, 520)
MAKE_RANDOM_WAR_DECK_BUTTON = (265, 490)
EXIT_MAKE_WAR_DECK_PAGE = (205, 40)

# War battle start + post-battle OK
START_WAR_BATTLE_BUTTON_COORDS = (280, 415)
OK_AFTER_WAR_BATTLE_COMPLETE_BUTTON_COORD = (205, 570)
# Playfield drop region during a war battle (LTRB → (left, top, right, bottom))
WAR_BATTLE_PLAYFIELD_LTRB = (55, 256, 360, 470)
# Full-board drop region for random/clean plays (LTRB), measured from a fight frame.
# Sits inside the rl-bot PLAY_REGION normalization rect, so it does not affect coord norm.
PLAYABLE_PLAY_REGION_LTRB = (59, 67, 355, 467)
# Safe deadspace tap on the war page (used to dismiss the battle-confirm overlay).
WAR_DEADSPACE_COORD = (20, 330)

# War boot: the clan-war results popup ("Your Clan didn't finish!" / reward chest)
# that can cover the main menu and intercept navigation to the war page.
WAR_BOOT_REWARD_COORD = (221, 382)  # the reward-chest "OPEN" button
SKIP_WAR_BOOT_BUTTON_COORDS = (208, 601)  # the bottom OK / skip button
CLAN_WAR_FINAL_RESULTS_POPUP_OK_BUTTON = (210, 526)  # OK button on the clan-war final-results popup

# --- Shop / daily free offer ---
CONFIRM_COLLECT_DAILY_FREE_OFFER_BUTTON_COORDS = (210, 440)
CONFIRM_FREE_REWARD_PURCHASE_1 = (207, 396)  # green FREE! button on the confirmation popup
SHOP_PAGE_DEADSPACE_COORD = (10, 280)
PAGINATE_SHOP_PAGE_BUTTON = (65, 600)

# --- Clan chat ---
CLAN_CHAT_FEED_SUBCROP = (0, 60, 419, 500)
CLAN_CHAT_FOOTER_SUBCROP = (0, 470, 280, 600)
CLAN_CHAT_REQUEST_PICKER_SUBCROP = (0, 70, 419, 600)
CLAN_CHAT_REQUEST_CARD_CLICK_OFFSET = (48, -40)
MORE_CLAN_CHAT_CARD_OPTIONS_SUBCROP = (17, 99, 76, 161)
REVEAL_MORE_CLAN_CHAT_CARD_OPTIONS_BUTTON_COORD = (50, 125)

# --- Fight: champion ability ---
CHAMPION_ABILITY_DISMISS_COORD = (330, 460)

# --- Post-battle result screen (Trophy Road / Classic 1v1) ---
# Yellow "Play Again" sits left of the blue OK button on the result screen.
PLAY_AGAIN_BUTTON_COORD = (154, 575)
# Bottom band holding the Play Again / OK buttons; limits template search.
POST_BATTLE_BUTTON_BAR_SUBCROP = (0, 540, 419, 610)
# find_image returns the template's top-left; the play_again_button crop is 88x36.
PLAY_AGAIN_TEMPLATE_CLICK_OFFSET = (44, 18)
# Band holding the "WINNER!" label above the bottom (own) crowns on a victory.
RESULT_VICTORY_BANNER_SUBCROP = (120, 235, 300, 285)
# Band holding the "WINNER!" label above the top (opponent) crowns on a defeat.
RESULT_DEFEAT_BANNER_SUBCROP = (120, 45, 300, 95)

# --- Battle: arena geometry (419x633, player at the bottom) ---
# Measured on 2026-09-15 frames (tests/fixtures/battle). River at y ~255-275; the
# player's half starts at the bridge foot; lanes split at the king towers' centre.
ARENA_LTRB = (55, 60, 365, 470)
LANE_SPLIT_X = 209
RIVER_Y = 283
# Rows from here down are the tower band: an enemy here is hitting a princess tower.
TOWER_BAND_Y = 330
AT_TOWER_MIN = 10  # enemy bar pixels in the tower band that count (empty arena ~4)
# Tower footprints (x1, y1, x2, y2). Each unit-bar mask excludes only the towers of its
# own colour (enemy red art for the enemy mask, our blue art for ours), so attackers
# standing on a tower are still counted. Our king box extends upward over its bar.
ENEMY_TOWER_BOXES = (
    (70, 75, 145, 155),
    (270, 75, 345, 155),
    (165, 15, 255, 80),
)
OUR_TOWER_BOXES = (
    (70, 355, 145, 432),
    (270, 355, 345, 432),
    (165, 400, 255, 482),
)
TOWER_BOXES = ENEMY_TOWER_BOXES + OUR_TOWER_BOXES
# Princess-tower health bars: (row y, x0, x1) of the filled bar at full health.
TOWER_HP_BARS = {
    "their_L": (94, 103, 141),
    "their_R": (94, 289, 327),
    "our_L": (394, 103, 141),
    "our_R": (394, 290, 327),
}
# Gold level badge left of each bar: present while the tower stands.
TOWER_BADGE_BOXES = {
    "their_L": (86, 86, 102, 102),
    "their_R": (272, 86, 288, 102),
    "our_L": (86, 386, 102, 402),
    "our_R": (273, 386, 289, 402),
}
# The emote picker (a row of white boxes) covers this band of our half while open.
EMOTE_PICKER_BAND = (60, 355, 360, 440)
EMOTE_PICKER_WHITE_MIN = 0.06  # near-white fraction of the band: ~0.12 open, <0.02 otherwise
ENEMY_PRESENCE_MIN = 15  # unit-bar pixels on our half that count as a push (a lone unit ~25)
TOWER_BAR_MIN_PIXELS = 4
TOWER_BAR_ROW_SEARCH = 3  # the bright fill row drifts a few px between arenas; scan y±3
TOWER_BADGE_MIN_PIXELS = 6
