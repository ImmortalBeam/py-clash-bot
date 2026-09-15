# Adaptive battle policy — design

Status: approved direction, pending implementation plan. Scope: 1v1 fights (Trophy Road, Classic 1v1) through `fight.py::_fight_loop`. 2v2 uses the same loop and inherits the change; war battles (`war.py`) and "Random card plays" are untouched.

## 1. Problem

Measured on the user's account (Trophy Road, ~2600 trophies) over a ten-match run on 2026-09-15 with frames captured every 4 s and every play logged:

- **The elixir strategy never runs.** `wait_for_elixir` (`fight.py:210-289`) short-circuits when `switch_side()` reports lane "activity" above `PLAY_THRESHOLD`. That activity number is an L2 norm of a `uint8` subtraction (`card_detection.py:11785`) against a single baseline snapshot taken at match start, so negative differences wrap to 255 and the value is always huge. In the two matches examined, 40 of 42 plays were triggered by this override. The phase/elixir tables in `BattleStrategy` are effectively dead.
- **Consequence: one card every ~6 s, alone.** Each card is dropped the moment one is affordable. Support troops walk in alone and die; spells (Zap, Fireball) are cast onto the tower whenever affordable for near-zero value.
- **Lane choice sends troops into the busier lane** (`play_side` = lane with the larger diff), i.e. into the enemy's push, and cannot tell our units from theirs.
- **Nothing reads the game.** No tower health, crowns, timer, or enemy presence (see survey in the session log; `friendly_crowns`/`enemy_crowns` in `logger.py` are dead fields).
- Win rate 44.5% before the placement retune; the retune alone did not change the above.

## 2. What the screen gives us (measured, 419x633 BGR)

| Signal | Where | How |
|---|---|---|
| Elixir count 0–10 | `ELIXIR_COORDS` row y=613, ten pips (`state_detect.py:187`) | count consecutive pips matching `ELIXIR_COLOR` (tol 65) from the left |
| Enemy units on the field | red unit health bars, RGB ≈ (205–230, 75–85, 70–85) | mask `r>185 & g<105 & b<105 & r−g>95`, arena only (x 55–365, y 60–470), tower boxes excluded; count per lane (split x=209) and per half (river y=283) |
| Our units on the field | blue unit health bars, RGB ≈ (50–105, 120–180, 195–255) | mask `b>185 & r<115 & 100<g<195`, same regions |
| Enemy princess tower HP | pink bar, row y=94, left x 103–141, right x ≈ 280–318 | fill fraction = rightmost pink px / full width (full width sampled at t=0) |
| Our princess tower HP | blue bar, row y=394, right x 289–327, left x ≈ 92–130 | same |
| Tower destroyed | no bar pixels in the bar box | HP = `None` |
| King tower activation | bar appears above/below king (enemy y ≈ 40–60, ours ≈ 440–460) | presence only; stage 2 |
| Elapsed time | wall clock from `BattleStrategy.start_battle()` | already exists; on-screen timer/overtime are stage 2 |

Validation from the run: enemy-on-our-half counts are 0–1 when the half is empty and 60–200 during real pushes (match 2 at 26–39 s and 117 s); our own units never register as enemy. Tower boxes to exclude: enemy princess (70–145, 75–155) and (270–345, 75–155), enemy king (165–255, 15–80), our princess (70–145, 355–432) and (270–345, 355–432), our king (165–255, 418–482). A small constant blue count (~8 left / ~53 right) exists on our half from static UI and is subtracted as a per-match baseline.

## 3. Architecture

Three units, each testable alone:

### 3.1 `pyclashbot/bot/battle_state.py` (new, leaf: numpy + `coords` + `image_rec` only)
- `@dataclass BattleState`: `elixir: int`, `enemy_our_half: tuple[int,int]` (left, right), `enemy_their_half`, `ours_their_half`, `tower_hp: dict[str, float | None]` keys `our_L, our_R, their_L, their_R`, `elapsed: float`.
- `read_battle_state(iar, elapsed, baseline: BattleBaseline | None) -> BattleState` — pure over a BGR array.
- `BattleBaseline` captured once at fight start: full-HP bar widths and the static blue/red counts to subtract.
- Helpers: `count_elixir_pips(iar)`, `unit_bar_masks(iar)`, `lane_counts(mask, half)`, `tower_hp_fraction(iar, tower, baseline)`.
- All geometry constants live in `coords.py` under `# --- Battle: arena geometry ---` (`ARENA_LTRB`, `LANE_SPLIT_X`, `RIVER_Y`, `TOWER_BOXES`, `TOWER_HP_BAR_ROWS/XRANGES`). `ELIXIR_COORDS` stays where it is (referenced, not moved).

### 3.2 `pyclashbot/bot/battle_policy.py` (new, pure)
- Roles derived from the existing `PLAY_COORDS` groups: `tank` (bridge_line), `win_condition` (bridge_rush), `chip` (goblin_barrel, miner, graveyard, goblin_drill), `support` (back_support, king_lane, princess, spirit), `building` (defense_building, siege_building), `small_spell` (reactive_spell, lane_spell, center_spell, tornado), `big_spell` (large_spell, rocket). Unknown card ⇒ `support`.
- `Mode`: `ahead` / `even` / `behind` from standing tower counts (`tower_hp is None` ⇒ destroyed); `endgame` flag when `elapsed > 150 s`.
- `Decision(kind, lane, roles, min_elixir, zone, reason)` where `kind ∈ {defend, attack, follow_up, chip, finish, hold}`.
- `decide(state, hand: list[HandCard], mode, push: PushMemory | None) -> Decision`, evaluated in this order:
  1. **Defend** if `enemy_our_half[lane] ≥ ENEMY_PRESENCE_MIN (25)`: lane = the fuller lane; roles `[building, support, tank, small_spell]`; `min_elixir` = 0 (play the first affordable); zone `defense`.
  2. **Follow-up** if a tank was played < 8 s ago in `push.lane` and `ours_their_half`/bridge shows it alive: roles `[support]`, zone `support_behind`, `min_elixir` 0.
  3. **Finish** if any enemy tower HP < 0.15 and a `big_spell` or `chip` is in hand: zone `spell_tower` / `chip`, lane of that tower.
  4. **Attack** if our half is clear and `elixir ≥ attack_threshold(mode)`: lane = weakest standing enemy tower (ties ⇒ our healthier side); roles `[tank, win_condition]`, zone `bridge`; records `PushMemory(lane, t)`.
  5. **Chip** if our half is clear, `chip` in hand and `elixir ≥ 5`: weakest tower.
  6. Otherwise **hold** (wait for elixir; re-evaluate every 0.5 s).
- `attack_threshold(mode)`: `ahead` 9, `even` 8, `behind` 7; after 150 s subtract 1; last 30 s and not ahead ⇒ 5 and roles `[tank, win_condition, support]`.
- Spells never fire outside Defend (small) or Finish (big); Zap-style spam ends.
- Card selection: first hand slot whose role is in `roles`, in role order, tie-broken by the existing anti-repeat deque.

### 3.3 `fight.py` integration
- `_fight_loop`: capture `BattleBaseline`; each tick: screenshot → `read_battle_state` → `decide` → if `hold`: sleep 0.5 and continue (with the existing battle-ended / detection-lost checks and the 40 s elixir timeout preserved); else identify affordable slots (`check_which_cards_are_available` + `identify_hand_cards`), pick by role, tap at the zone coordinates, log the decision (`kind lane reason`) in the status line, record play.
- `wait_for_elixir`, `switch_side` usage and the `BattleStrategy` elixir tables are removed from the 1v1 path. `BattleStrategy` keeps `start_battle/get_elapsed_time` (used by recording and 2v2).
- Champion-ability trigger and emotes stay as they are.
- Placement zones added to `PLAY_COORDS`: `defense` (in front of each princess tower, in lane: left (115, 340), (100, 352); right (295, 340), (310, 352)), `support_behind` (= current back_support band), `spell_defense` (left (115, 335), right (295, 335)), `bridge` (= bridge_line band), `chip`/`spell_tower` (= existing per-card tables). Zone lookup is by role → group so per-card coordinates remain the source of truth.

## 4. Failure handling
- Any reader returning nonsense (all towers `None`, elixir 0 for > 40 s) falls back to the previous behaviour for the rest of that fight: `decide` returns `attack` at 7 on a random lane. Logged once.
- Card identification failure ⇒ role `support`; still played, never blocks.
- Detection-lost / battle-ended logic unchanged.

## 5. Testing
- **Fixtures** from the 2026-09-15 run (`tests/fixtures/battle/*.png`, names masked where needed): empty arena at t=0, enemy push on our left (match 2, 35 s), our push on their left (match 2, 78 s), damaged enemy tower (match 2, 126 s), our tower destroyed (match 2, 148 s).
- `tests/test_battle_state.py`: elixir count, per-lane enemy/ours counts (thresholds above/below 25), tower HP fractions within ±0.12 of the on-screen numbers, `None` for the destroyed tower.
- `tests/test_battle_policy.py`: pure decision tests for each rule and mode, including the ordering (defend beats attack), thresholds, follow-up window, finish rule, endgame.
- `tests/test_fight_loop_policy.py`: stubbed emulator/time (pattern of `test_play_again_state.py`), asserting the loop taps the chosen slot and zone, holds when told to, and respects timeouts.
- Live: the ten-match runner (`scratchpad/run10.py`, to be kept as `scripts/run_matches.py`) before/after; success = win rate above the 44.5% baseline over ten matches and no fight-loop failures.

## 6. Out of scope (stage 2)
On-screen timer and overtime, king-tower activation as a signal, precise spell aiming at unit clusters, enemy elixir estimation, opponent deck memory.
