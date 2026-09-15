# Changes in this fork

Based on py-clash-bot upstream (`34d11e5`). All changes are in `pyclashbot/` and `tests/`, with offline tests for each.

## New: Play Again after 1v1 battles

- After a Trophy Road or Classic 1v1 battle the bot now presses **Play Again** on the result screen instead of pressing OK and going back through the main menu and the whole job list.
- New GUI job **"Play again"** under Battles, with a **Fights** spinbox. The bot presses Play Again up to that many times in a row, then takes the normal OK path once so upgrades, shop, and clan jobs still run. Default 5. Toggle off gives the original behaviour. 2v2 is unchanged.
- Win/loss is read directly from the result screen before Play Again is pressed, so the stats stay correct for chained fights. Draws are recorded as unknown and not counted.
- Detection uses pixel fingerprints with template-image fallbacks for the Play Again button and the WINNER! label on both win and loss screens. Popups on the result screen (trophy reward, reward choice) are dismissed first. If the button never appears, the bot falls back to the old OK path.
- Implemented as a new `play_again` state in the state machine, so failures are reported under their own state name.

## New: adaptive battle policy

- The fight loop now reads the battle every half second: elixir, enemy troops on our half per lane (red health bars), our troops on their half, and all four princess-tower healths (`pyclashbot/bot/battle_state.py`).
- A pure policy (`pyclashbot/bot/battle_policy.py`) turns that into one decision: defend the threatened lane first with the cheapest fitting card in front of the tower; follow a tank with support within 8 s; finish a tower under 15% with a big spell or chip card; otherwise push the weakest enemy tower with a tank at the bridge once elixir reaches a score-dependent threshold (ahead 9, even 8, behind 7, one less in double elixir, 5 in the last 30 s when not ahead); chip with spare elixir (7) and no push in the last 15 s; else hold.
- Spells are no longer thrown at the tower whenever affordable: small spells only defend, big spells only finish.
- The old "battle too active" override, which fired on almost every play because it compared unsigned bytes and wrapped, is gone along with the elixir-phase tables and busier-lane placement. Random card plays and war battles are unchanged.
- Baseline before this change (2026-09-15, six Trophy Road matches, forward placement only): 2 wins, 4 losses.

## Changed: forward troop placement

- Tanks (`bridge_line`) now start at the bridge foot instead of mid-field; support troops (`back_support`, `king_lane`) start one to two tiles behind the bridge instead of beside the king tower; unrecognised cards fall back to the same band instead of the back field. The bot has no tank-then-support sequencing, so deep plays only cost walking time. Spells, buildings, spirits and tunnelling cards are unchanged. `docs/placement-zones.md` updated.

## Fixed

- **Gift popup loop while waiting for a match.** The tap used to "wake" the screen while waiting for matchmaking landed on the daily-gift icon of the main menu. If the search was cancelled, the bot opened and closed the gift popup three times a second for two minutes. Moved to a real dead spot.
- **Main-menu wait gave up on a popup race.** After boot, the Trophy Road rewards page can open a second after the main menu appears. The wait confirmed the menu once, saw the popup, and failed instead of dismissing it. It now keeps polling and handling popups until the timeout.
- **Type checking on Windows.** The `ty` checker is pinned to the Linux platform so local lint matches CI instead of failing on Windows-only false positives.

## Tests

- 93 offline tests, including new fixture-based tests with real 419x633 result-screen and main-menu screenshots (player names masked).
- New live emulator test `play_again` in the Clash Royale suite: plays a battle, presses Play Again, plays a second battle, exits via OK, and checks both results were counted.
