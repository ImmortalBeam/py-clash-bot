# Adaptive Battle Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken "battle too active" timing and busier-lane placement with a policy that reads elixir, enemy presence per lane, and tower health from the screen, then defends, attacks the weakest tower with tank-then-support, and adapts thresholds to the score.

**Architecture:** Three pure units feed the fight loop: `battle_state.py` (screenshot → `BattleState`), `battle_policy.py` (`BattleState` + hand → `Decision`), and placement zones in `card_detection.PLAY_COORDS`. `fight._fight_loop` becomes a read → decide → act loop; `wait_for_elixir`/`switch_side` leave the 1v1 path. Everything is unit-tested on real 419x633 frames captured on 2026-09-15.

**Tech Stack:** Python 3.12, numpy, OpenCV (cv2), pytest, `uv run`, ruff, ty. Screenshots are BGR numpy arrays `(633, 419, 3)`.

**Spec:** `docs/superpowers/specs/2026-09-15-adaptive-battle-policy-design.md`

## Global Constraints

- All screen coordinates as named constants in `pyclashbot/bot/coords.py` (exception: `PLAY_COORDS` in `card_detection.py`).
- `battle_state.py` and `battle_policy.py` are leaf modules: import only numpy, `pyclashbot.bot.coords`, `pyclashbot.bot.state_detect` (for `ELIXIR_COORDS`/`ELIXIR_COLOR`), `pyclashbot.detection.image_rec`. Never from `fight`, `nav`, `card_detection`.
- Screenshots are BGR; write masks with explicit channel indices `[..., 0]=B, [..., 1]=G, [..., 2]=R`.
- Tests offline by default (`uv run pytest`); the live check uses `--integration --emulator adb --adb-serial 127.0.0.1:5565`.
- Before every commit: `uvx pre-commit run --files <changed files>` must pass (ruff, ruff-format, ty). Conventional commit messages. Never `--no-verify`.
- Work in `C:\Users\HomePC\Downloads\GitHub\ClashRoyaleBotAdvanced\AdvancedBot` on `master`.
- Do not touch `_random_fight_loop`, `war.py`, or 2v2-specific code paths except where `_fight_loop` is shared.

---

### Task 1: Arena geometry constants and battle fixtures

**Files:**
- Modify: `pyclashbot/bot/coords.py` (append a section at the end)
- Create: `tests/fixtures/battle/t000_empty.png`, `t035_enemy_push_left.png`, `t078_our_push_left.png`, `t126_enemy_tower_damaged.png`, `t148_our_tower_destroyed.png`
- Test: `tests/test_battle_fixtures.py`

**Interfaces:**
- Produces constants: `ARENA_LTRB = (55, 60, 365, 470)`, `LANE_SPLIT_X = 209`, `RIVER_Y = 283`, `TOWER_BOXES: tuple[tuple[int,int,int,int], ...]` (x1, y1, x2, y2), `TOWER_HP_BARS: dict[str, tuple[int, int, int]]` (row y, x0, x1) keyed `our_L, our_R, their_L, their_R`, `TOWER_BADGE_BOXES: dict[str, tuple[int,int,int,int]]`, `ENEMY_PRESENCE_MIN = 25`, `TOWER_BAR_MIN_PIXELS = 4`, `TOWER_BADGE_MIN_PIXELS = 6`.

- [ ] **Step 1: Copy and mask the fixture frames**

Source frames are in the session scratchpad `run10_out/match_02/frames/` (`0000.png`, `0035.png`, `0078.png`, `0126.png`, `0148.png`). Mask the opponent name at the top-left before committing:

```python
# scratch script, run with: uv run python <file>
import cv2, os
SRC = r"C:\Users\HomePC\AppData\Local\Temp\claude\C--Users-HomePC-Downloads-GitHub-ClashRoyaleBotAdvanced-py-clash-bot\bcca2a82-a6da-4888-aa36-f0fc828b8bc5\scratchpad\run10_out\match_02\frames"
DST = "tests/fixtures/battle"
os.makedirs(DST, exist_ok=True)
for src, dst in [("0000", "t000_empty"), ("0035", "t035_enemy_push_left"), ("0078", "t078_our_push_left"),
                 ("0126", "t126_enemy_tower_damaged"), ("0148", "t148_our_tower_destroyed")]:
    im = cv2.imread(os.path.join(SRC, src + ".png"))
    im[0:36, 0:130] = (40, 30, 20)  # opponent name / clan
    cv2.imwrite(os.path.join(DST, dst + ".png"), im, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print(dst, im.shape)
```

- [ ] **Step 2: Write the failing test**

`tests/test_battle_fixtures.py`:

```python
"""Battle fixtures are real 419x633 BGR frames; geometry constants must agree with them."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from pyclashbot.bot.coords import ARENA_LTRB, LANE_SPLIT_X, RIVER_Y, TOWER_BOXES, TOWER_HP_BARS

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "battle"
NAMES = [
    "t000_empty",
    "t035_enemy_push_left",
    "t078_our_push_left",
    "t126_enemy_tower_damaged",
    "t148_our_tower_destroyed",
]


def load(name: str) -> np.ndarray:
    im = cv2.imread(str(FIXTURES / f"{name}.png"))
    assert im is not None, name
    return im


@pytest.mark.parametrize("name", NAMES)
def test_fixture_is_full_frame(name) -> None:
    assert load(name).shape == (633, 419, 3)


def test_geometry_is_inside_the_frame() -> None:
    left, top, right, bottom = ARENA_LTRB
    assert 0 <= left < LANE_SPLIT_X < right <= 419
    assert 0 <= top < RIVER_Y < bottom <= 633
    for x1, y1, x2, y2 in TOWER_BOXES:
        assert 0 <= x1 < x2 <= 419 and 0 <= y1 < y2 <= 633
    for y, x0, x1 in TOWER_HP_BARS.values():
        assert 0 <= y < 633 and 0 <= x0 < x1 <= 419
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_battle_fixtures.py -q`
Expected: ImportError, `cannot import name 'ARENA_LTRB'`.

- [ ] **Step 4: Add the constants**

Append to `pyclashbot/bot/coords.py`:

```python
# --- Battle: arena geometry (419x633, player at the bottom) ---
# Measured on 2026-09-15 frames (tests/fixtures/battle). River at y ~255-275; the
# player's half starts at the bridge foot; lanes split at the king towers' centre.
ARENA_LTRB = (55, 60, 365, 470)
LANE_SPLIT_X = 209
RIVER_Y = 283
# Tower footprints (x1, y1, x2, y2) excluded from unit-bar counting: enemy princess L/R,
# enemy king, our princess L/R, our king (extended upward to cover its health bar).
TOWER_BOXES = (
    (70, 75, 145, 155),
    (270, 75, 345, 155),
    (165, 15, 255, 80),
    (70, 355, 145, 432),
    (270, 355, 345, 432),
    (165, 400, 255, 482),
)
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
ENEMY_PRESENCE_MIN = 25  # unit-bar pixels on our half that count as a push
TOWER_BAR_MIN_PIXELS = 4
TOWER_BADGE_MIN_PIXELS = 6
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_battle_fixtures.py -q`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
uvx pre-commit run --files pyclashbot/bot/coords.py tests/test_battle_fixtures.py
git add pyclashbot/bot/coords.py tests/test_battle_fixtures.py tests/fixtures/battle
git commit -m "chore(fixtures): battle frames and arena geometry constants"
```

---

### Task 2: `battle_state.py` — read elixir, units per lane, tower health

**Files:**
- Create: `pyclashbot/bot/battle_state.py`
- Test: `tests/test_battle_state.py`

**Interfaces:**
- Consumes: Task 1 constants; `ELIXIR_COORDS`, `ELIXIR_COLOR` from `pyclashbot.bot.state_detect`; `pixel_is_equal` from `pyclashbot.detection.image_rec`.
- Produces:
  - `@dataclass(frozen=True) BattleState(elixir: int, enemy_our_half: tuple[int, int], enemy_their_half: tuple[int, int], ours_their_half: tuple[int, int], tower_hp: dict[str, float | None], elapsed: float)` with methods `threatened_lane() -> str | None` ("left"/"right"/None), `standing_towers(side: str) -> int` (side "our"/"their"), `weakest_enemy_lane() -> str | None`.
  - `count_elixir_pips(iar) -> int`
  - `unit_bar_masks(iar) -> tuple[np.ndarray, np.ndarray]` (enemy_mask, ours_mask), bool arrays `(633, 419)`
  - `lane_counts(mask, half: str) -> tuple[int, int]`
  - `tower_standing(iar, tower: str) -> bool`
  - `tower_hp_fraction(iar, tower: str) -> float | None`
  - `read_battle_state(iar, elapsed: float) -> BattleState`

- [ ] **Step 1: Write the failing tests**

`tests/test_battle_state.py`:

```python
"""battle_state: one BGR frame -> elixir, units per lane, tower health."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from pyclashbot.bot.battle_state import (
    BattleState,
    count_elixir_pips,
    lane_counts,
    read_battle_state,
    tower_hp_fraction,
    tower_standing,
    unit_bar_masks,
)
from pyclashbot.bot.coords import ENEMY_PRESENCE_MIN

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "battle"


def load(name: str) -> np.ndarray:
    im = cv2.imread(str(FIXTURES / f"{name}.png"))
    assert im is not None, name
    return im


def test_elixir_pips_counted_from_the_left() -> None:
    assert count_elixir_pips(load("t000_empty")) == 8
    assert count_elixir_pips(load("t126_enemy_tower_damaged")) == 5


def test_empty_arena_has_no_units_on_either_half() -> None:
    enemy, ours = unit_bar_masks(load("t000_empty"))
    assert max(lane_counts(enemy, "our")) < ENEMY_PRESENCE_MIN
    assert max(lane_counts(enemy, "their")) < ENEMY_PRESENCE_MIN
    assert max(lane_counts(ours, "their")) < ENEMY_PRESENCE_MIN


def test_enemy_push_on_our_left_is_seen_in_the_left_lane_only() -> None:
    enemy, ours = unit_bar_masks(load("t035_enemy_push_left"))
    left, right = lane_counts(enemy, "our")
    assert left >= ENEMY_PRESENCE_MIN
    assert right < ENEMY_PRESENCE_MIN
    assert max(lane_counts(ours, "our")) < ENEMY_PRESENCE_MIN  # our own units never count as enemy


def test_our_push_on_their_left_is_seen_as_ours_not_enemy() -> None:
    enemy, ours = unit_bar_masks(load("t078_our_push_left"))
    left, right = lane_counts(ours, "their")
    assert left >= ENEMY_PRESENCE_MIN
    assert max(lane_counts(enemy, "our")) < ENEMY_PRESENCE_MIN


def test_full_health_towers_read_near_one() -> None:
    im = load("t000_empty")
    for tower in ("our_L", "our_R", "their_L", "their_R"):
        hp = tower_hp_fraction(im, tower)
        assert hp is not None and hp >= 0.9, tower


def test_damaged_enemy_tower_reads_lower() -> None:
    hp = tower_hp_fraction(load("t126_enemy_tower_damaged"), "their_L")
    assert hp is not None and 0.55 <= hp <= 0.9  # on-screen 1984/2534 = 0.78; text overlaps the bar
    assert tower_hp_fraction(load("t126_enemy_tower_damaged"), "their_R") >= 0.9


def test_destroyed_tower_reads_none() -> None:
    im = load("t148_our_tower_destroyed")
    assert tower_standing(im, "our_L") is False
    assert tower_hp_fraction(im, "our_L") is None
    assert tower_standing(im, "our_R") is True
    assert tower_hp_fraction(im, "our_R") >= 0.9


def test_read_battle_state_assembles_everything() -> None:
    state = read_battle_state(load("t035_enemy_push_left"), elapsed=35.0)
    assert isinstance(state, BattleState)
    assert state.elapsed == 35.0
    assert state.threatened_lane() == "left"
    assert state.standing_towers("our") == 2
    assert state.standing_towers("their") == 2


def test_weakest_enemy_lane_prefers_the_damaged_tower() -> None:
    state = read_battle_state(load("t126_enemy_tower_damaged"), elapsed=126.0)
    assert state.weakest_enemy_lane() == "left"


def test_weakest_enemy_lane_is_none_when_both_towers_are_gone() -> None:
    state = BattleState(5, (0, 0), (0, 0), (0, 0), {"our_L": 1.0, "our_R": 1.0, "their_L": None, "their_R": None}, 10.0)
    assert state.weakest_enemy_lane() is None
    assert state.standing_towers("their") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_battle_state.py -q`
Expected: ImportError on `pyclashbot.bot.battle_state`.

- [ ] **Step 3: Implement `battle_state.py`**

```python
"""Pure readers that turn one in-battle screenshot (BGR, 633x419) into a BattleState.

Leaf module: imports only numpy, coords, state_detect (elixir pips) and image_rec.
Nothing here clicks or waits.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pyclashbot.bot.coords import (
    ARENA_LTRB,
    ENEMY_PRESENCE_MIN,
    LANE_SPLIT_X,
    RIVER_Y,
    TOWER_BADGE_BOXES,
    TOWER_BADGE_MIN_PIXELS,
    TOWER_BAR_MIN_PIXELS,
    TOWER_BOXES,
    TOWER_HP_BARS,
)
from pyclashbot.bot.state_detect import ELIXIR_COLOR, ELIXIR_COORDS
from pyclashbot.detection.image_rec import pixel_is_equal

TOWERS = ("our_L", "our_R", "their_L", "their_R")


@dataclass(frozen=True)
class BattleState:
    elixir: int
    enemy_our_half: tuple[int, int]  # (left, right) enemy unit-bar pixels on our half
    enemy_their_half: tuple[int, int]
    ours_their_half: tuple[int, int]
    tower_hp: dict[str, float | None]  # keys TOWERS; None = destroyed
    elapsed: float

    def threatened_lane(self) -> str | None:
        left, right = self.enemy_our_half
        if max(left, right) < ENEMY_PRESENCE_MIN:
            return None
        return "left" if left >= right else "right"

    def standing_towers(self, side: str) -> int:
        return sum(1 for key in (f"{side}_L", f"{side}_R") if self.tower_hp.get(key) is not None)

    def weakest_enemy_lane(self) -> str | None:
        candidates = [(hp, lane) for lane, key in (("left", "their_L"), ("right", "their_R")) if (hp := self.tower_hp.get(key)) is not None]
        if not candidates:
            return None
        return min(candidates)[1]


def count_elixir_pips(iar: np.ndarray) -> int:
    count = 0
    for y, x in ELIXIR_COORDS:
        if not pixel_is_equal(iar[y][x], ELIXIR_COLOR, tol=65):
            break
        count += 1
    return count


def unit_bar_masks(iar: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Enemy (red) and friendly (blue) unit health-bar pixels inside the arena, towers excluded."""
    b = iar[..., 0].astype(int)
    g = iar[..., 1].astype(int)
    r = iar[..., 2].astype(int)
    enemy = (r > 185) & (g < 105) & (b < 105) & (r - g > 95)
    ours = (b > 185) & (r < 115) & (g > 100) & (g < 195)
    keep = np.zeros(iar.shape[:2], dtype=bool)
    left, top, right, bottom = ARENA_LTRB
    keep[top:bottom, left:right] = True
    for x1, y1, x2, y2 in TOWER_BOXES:
        keep[y1:y2, x1:x2] = False
    return enemy & keep, ours & keep


def lane_counts(mask: np.ndarray, half: str) -> tuple[int, int]:
    """(left, right) pixel counts of `mask` on the given half ("our" below the river, "their" above)."""
    _, top, _, bottom = ARENA_LTRB
    rows = mask[RIVER_Y:bottom] if half == "our" else mask[top:RIVER_Y]
    return int(rows[:, :LANE_SPLIT_X].sum()), int(rows[:, LANE_SPLIT_X:].sum())


def tower_standing(iar: np.ndarray, tower: str) -> bool:
    """The gold level badge next to the health bar is only drawn while the tower stands."""
    x1, y1, x2, y2 = TOWER_BADGE_BOXES[tower]
    box = iar[y1:y2, x1:x2].astype(int)
    gold = (box[..., 2] > 190) & (box[..., 1] > 140) & (box[..., 0] < 100)
    return int(gold.sum()) >= TOWER_BADGE_MIN_PIXELS


def tower_hp_fraction(iar: np.ndarray, tower: str) -> float | None:
    """Filled fraction of the princess-tower bar, or None when the tower is gone.

    The number printed over the bar hides part of the fill, so readings run ~0.1 low
    on damaged towers; callers should treat values as coarse (healthy / damaged / low).
    """
    if not tower_standing(iar, tower):
        return None
    y, x0, x1 = TOWER_HP_BARS[tower]
    row = iar[y, x0 : x1 + 1].astype(int)
    if tower.startswith("their"):
        filled = (row[:, 2] > 200) & (row[:, 0] > 100) & (row[:, 1] < 130)  # pink
    else:
        filled = (row[:, 0] > 200) & (row[:, 2] < 140) & (row[:, 1] > 120)  # blue
    idx = np.where(filled)[0]
    if len(idx) < TOWER_BAR_MIN_PIXELS:
        return 0.05  # standing but almost no bar visible: nearly dead
    return min(1.0, float(idx.max() + 1) / float(x1 - x0 + 1))


def read_battle_state(iar: np.ndarray, elapsed: float) -> BattleState:
    enemy, ours = unit_bar_masks(iar)
    return BattleState(
        elixir=count_elixir_pips(iar),
        enemy_our_half=lane_counts(enemy, "our"),
        enemy_their_half=lane_counts(enemy, "their"),
        ours_their_half=lane_counts(ours, "their"),
        tower_hp={tower: tower_hp_fraction(iar, tower) for tower in TOWERS},
        elapsed=elapsed,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_battle_state.py -q`
Expected: 10 passed. If `test_destroyed_tower_reads_none` or the badge assertions fail, print `gold.sum()` for each badge box on `t000_empty` and `t148_our_tower_destroyed` and adjust `TOWER_BADGE_BOXES` / the gold thresholds in coords/battle_state until standing towers give ≥ 6 and the destroyed one gives < 6; do not loosen the test.

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files pyclashbot/bot/battle_state.py tests/test_battle_state.py pyclashbot/bot/coords.py
git add pyclashbot/bot/battle_state.py tests/test_battle_state.py pyclashbot/bot/coords.py
git commit -m "feat(battle): read elixir, units per lane and tower health from a frame"
```

---

### Task 3: `battle_policy.py` — decide what, where and when

**Files:**
- Create: `pyclashbot/bot/battle_policy.py`
- Test: `tests/test_battle_policy.py`

**Interfaces:**
- Consumes: `BattleState` (Task 2).
- Produces:
  - `ROLE_OF_GROUP: dict[str, str]` mapping `PLAY_COORDS` group names → role; `role_for_group(group: str) -> str` (unknown → `"support"`).
  - `@dataclass(frozen=True) HandCard(slot: int, card_id: str, role: str)`
  - `@dataclass PushMemory(lane: str, started_at: float)`
  - `@dataclass(frozen=True) Decision(kind: str, lane: str | None, roles: tuple[str, ...], min_elixir: int, zone: str, reason: str)`; `kind ∈ {"defend", "follow_up", "finish", "attack", "chip", "hold"}`; `zone ∈ {"defense", "support_behind", "spell_tower", "chip", "bridge", "none"}`.
  - `game_mode(state: BattleState) -> str` → `"ahead" | "even" | "behind"`
  - `attack_threshold(mode: str, elapsed: float) -> int`
  - `decide(state: BattleState, hand: list[HandCard], push: PushMemory | None) -> Decision`
  - `choose_slot(hand: list[HandCard], roles: tuple[str, ...], recent: list[int]) -> HandCard | None`
  - Constants: `FOLLOW_UP_WINDOW_S = 8.0`, `FINISH_HP = 0.15`, `ENDGAME_S = 150.0`, `LAST_SECONDS_S = 30.0`, `MATCH_LENGTH_S = 180.0`, `CHIP_MIN_ELIXIR = 5`.

- [ ] **Step 1: Write the failing tests**

`tests/test_battle_policy.py`:

```python
"""battle_policy: pure decisions from a BattleState and the hand."""

from __future__ import annotations

from pyclashbot.bot.battle_policy import (
    CHIP_MIN_ELIXIR,
    Decision,
    HandCard,
    PushMemory,
    attack_threshold,
    choose_slot,
    decide,
    game_mode,
    role_for_group,
)
from pyclashbot.bot.battle_state import BattleState

FULL = {"our_L": 1.0, "our_R": 1.0, "their_L": 1.0, "their_R": 1.0}


def state(elixir=8, enemy_our=(0, 0), ours_their=(0, 0), hp=None, elapsed=60.0) -> BattleState:
    return BattleState(elixir, enemy_our, (0, 0), ours_their, dict(hp or FULL), elapsed)


HAND = [
    HandCard(0, "knight", "tank"),
    HandCard(1, "musketeer", "support"),
    HandCard(2, "cannon", "building"),
    HandCard(3, "zap", "small_spell"),
]


def test_roles_come_from_placement_groups() -> None:
    assert role_for_group("bridge_line") == "tank"
    assert role_for_group("bridge_rush") == "win_condition"
    assert role_for_group("back_support") == "support"
    assert role_for_group("defense_building") == "building"
    assert role_for_group("reactive_spell") == "small_spell"
    assert role_for_group("large_spell") == "big_spell"
    assert role_for_group("goblin_barrel") == "chip"
    assert role_for_group("No group") == "support"


def test_game_mode_from_standing_towers() -> None:
    assert game_mode(state()) == "even"
    assert game_mode(state(hp={**FULL, "their_L": None})) == "ahead"
    assert game_mode(state(hp={**FULL, "our_R": None})) == "behind"
    assert game_mode(state(hp={**FULL, "our_R": None, "their_L": None})) == "even"


def test_attack_threshold_by_mode_and_time() -> None:
    assert attack_threshold("ahead", 60.0) == 9
    assert attack_threshold("even", 60.0) == 8
    assert attack_threshold("behind", 60.0) == 7
    assert attack_threshold("even", 160.0) == 7  # after 150 s one less
    assert attack_threshold("even", 170.0) == 5  # last 30 s, not ahead
    assert attack_threshold("ahead", 170.0) == 8  # last 30 s, ahead: only the endgame discount


def test_defend_beats_everything_when_enemies_are_on_our_half() -> None:
    d = decide(state(elixir=10, enemy_our=(80, 0)), HAND, None)
    assert d.kind == "defend" and d.lane == "left" and d.zone == "defense"
    assert d.roles[0] == "building" and d.min_elixir == 0


def test_hold_when_below_attack_threshold_and_nothing_to_do() -> None:
    d = decide(state(elixir=6), HAND, None)
    assert d.kind == "hold" and d.min_elixir == 8


def test_attack_targets_the_weakest_enemy_tower_at_threshold() -> None:
    d = decide(state(elixir=8, hp={**FULL, "their_R": 0.4}), HAND, None)
    assert d.kind == "attack" and d.lane == "right" and d.zone == "bridge"
    assert d.roles == ("tank", "win_condition")


def test_follow_up_after_a_recent_tank_play() -> None:
    d = decide(state(elixir=4, elapsed=50.0), HAND, PushMemory("left", started_at=45.0))
    assert d.kind == "follow_up" and d.lane == "left" and d.zone == "support_behind"
    assert d.roles == ("support",)


def test_follow_up_expires_after_the_window() -> None:
    d = decide(state(elixir=4, elapsed=60.0), HAND, PushMemory("left", started_at=45.0))
    assert d.kind == "hold"


def test_finish_low_tower_with_big_spell_or_chip() -> None:
    hand = [*HAND[:2], HandCard(2, "fireball", "big_spell"), HAND[3]]
    d = decide(state(elixir=4, hp={**FULL, "their_L": 0.1}), hand, None)
    assert d.kind == "finish" and d.lane == "left" and d.zone == "spell_tower"


def test_chip_when_clear_and_affordable() -> None:
    hand = [HandCard(0, "goblin_barrel", "chip"), *HAND[1:]]
    d = decide(state(elixir=CHIP_MIN_ELIXIR), hand, None)
    assert d.kind == "chip" and d.zone == "chip"


def test_no_attack_when_no_enemy_tower_lane_is_known() -> None:
    d = decide(state(elixir=10, hp={**FULL, "their_L": None, "their_R": None}), HAND, None)
    assert d.kind == "hold"


def test_choose_slot_follows_role_order_then_avoids_recent() -> None:
    hand = [HandCard(0, "musketeer", "support"), HandCard(1, "archers", "support"), HandCard(2, "knight", "tank")]
    assert choose_slot(hand, ("tank", "support"), recent=[]) == hand[2]
    assert choose_slot(hand, ("support",), recent=[0]) == hand[1]
    assert choose_slot(hand, ("building",), recent=[]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_battle_policy.py -q`
Expected: ImportError on `pyclashbot.bot.battle_policy`.

- [ ] **Step 3: Implement `battle_policy.py`**

```python
"""Pure battle decisions: BattleState + hand -> Decision. No screen I/O, no clicks."""

from __future__ import annotations

from dataclasses import dataclass

from pyclashbot.bot.battle_state import BattleState

FOLLOW_UP_WINDOW_S = 8.0
FINISH_HP = 0.15
ENDGAME_S = 150.0
LAST_SECONDS_S = 30.0
MATCH_LENGTH_S = 180.0
CHIP_MIN_ELIXIR = 5

# PLAY_COORDS group -> role. Unknown groups (and "No group") are support.
ROLE_OF_GROUP: dict[str, str] = {
    "bridge_line": "tank",
    "bridge_rush": "win_condition",
    "back_support": "support",
    "king_lane": "support",
    "princess": "support",
    "spirit": "support",
    "defense_building": "building",
    "siege_building": "building",
    "reactive_spell": "small_spell",
    "lane_spell": "small_spell",
    "center_spell": "small_spell",
    "tornado": "small_spell",
    "large_spell": "big_spell",
    "rocket": "big_spell",
    "goblin_barrel": "chip",
    "graveyard": "chip",
    "miner": "chip",
    "goblin_drill": "chip",
}


def role_for_group(group: str) -> str:
    return ROLE_OF_GROUP.get(group, "support")


@dataclass(frozen=True)
class HandCard:
    slot: int
    card_id: str
    role: str


@dataclass
class PushMemory:
    lane: str
    started_at: float


@dataclass(frozen=True)
class Decision:
    kind: str  # defend | follow_up | finish | attack | chip | hold
    lane: str | None
    roles: tuple[str, ...]
    min_elixir: int
    zone: str  # defense | support_behind | spell_tower | chip | bridge | none
    reason: str


def game_mode(state: BattleState) -> str:
    ours, theirs = state.standing_towers("our"), state.standing_towers("their")
    if ours > theirs:
        return "ahead"
    if ours < theirs:
        return "behind"
    return "even"


def attack_threshold(mode: str, elapsed: float) -> int:
    threshold = {"ahead": 9, "even": 8, "behind": 7}[mode]
    if elapsed >= ENDGAME_S:
        threshold -= 1
    if elapsed >= MATCH_LENGTH_S - LAST_SECONDS_S and mode != "ahead":
        threshold = min(threshold, 5)
    return threshold


def _has_role(hand: list[HandCard], *roles: str) -> bool:
    return any(card.role in roles for card in hand)


def decide(state: BattleState, hand: list[HandCard], push: PushMemory | None) -> Decision:
    mode = game_mode(state)

    lane = state.threatened_lane()
    if lane is not None:
        return Decision("defend", lane, ("building", "support", "tank", "small_spell"), 0, "defense", f"enemy on our {lane}")

    if push is not None and state.elapsed - push.started_at <= FOLLOW_UP_WINDOW_S and _has_role(hand, "support"):
        return Decision("follow_up", push.lane, ("support",), 0, "support_behind", f"support the {push.lane} push")

    for lane_name, key in (("left", "their_L"), ("right", "their_R")):
        hp = state.tower_hp.get(key)
        if hp is not None and hp < FINISH_HP:
            if _has_role(hand, "big_spell"):
                return Decision("finish", lane_name, ("big_spell",), 0, "spell_tower", f"finish {lane_name} tower")
            if _has_role(hand, "chip"):
                return Decision("finish", lane_name, ("chip",), 0, "chip", f"finish {lane_name} tower")

    target = state.weakest_enemy_lane()
    threshold = attack_threshold(mode, state.elapsed)
    if target is not None and state.elixir >= threshold and _has_role(hand, "tank", "win_condition"):
        return Decision("attack", target, ("tank", "win_condition"), threshold, "bridge", f"{mode}: push {target} at {threshold}")

    if target is not None and state.elixir >= CHIP_MIN_ELIXIR and _has_role(hand, "chip"):
        return Decision("chip", target, ("chip",), CHIP_MIN_ELIXIR, "chip", f"chip {target} tower")

    if target is not None and state.elixir >= threshold and _has_role(hand, "support"):
        # No tank in hand: lead with support rather than sit on full elixir.
        return Decision("attack", target, ("support",), threshold, "bridge", f"{mode}: support push {target}")

    return Decision("hold", None, (), threshold, "none", f"{mode}: wait for {threshold} elixir")


def choose_slot(hand: list[HandCard], roles: tuple[str, ...], recent: list[int]) -> HandCard | None:
    for role in roles:
        matching = [card for card in hand if card.role == role]
        if not matching:
            continue
        fresh = [card for card in matching if card.slot not in recent]
        return (fresh or matching)[0]
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_battle_policy.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files pyclashbot/bot/battle_policy.py tests/test_battle_policy.py
git add pyclashbot/bot/battle_policy.py tests/test_battle_policy.py
git commit -m "feat(battle): pure policy deciding defend, attack, follow-up, finish, chip or hold"
```

---

### Task 4: Placement zones for decisions

**Files:**
- Modify: `pyclashbot/bot/card_detection.py` (`PLAY_COORDS` block near line 13, and after `calculate_play_coords`)
- Test: `tests/test_placement_coords.py` (append)

**Interfaces:**
- Consumes: `PLAY_COORDS`, `get_card_group`, `calculate_play_coords` (existing).
- Produces: new `PLAY_COORDS` groups `"defense"` and `"spell_defense"`; `zone_play_coords(zone: str, lane: str, card_group: str) -> tuple[int, int] | None`.

Zone semantics: `defense` → `PLAY_COORDS["defense"]` for troops and buildings, `PLAY_COORDS["spell_defense"]` for spell groups; `support_behind` → `PLAY_COORDS["back_support"]`; `bridge` → `PLAY_COORDS["bridge_line"]` for tanks/support, the card's own group for `bridge_rush`; `chip` and `spell_tower` → the card's own group table (Goblin Barrel, Miner, Fireball, Rocket… already aim at the tower); `none` → `None`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_placement_coords.py`)

```python
from pyclashbot.bot.card_detection import zone_play_coords


def test_defense_zone_is_in_front_of_our_towers() -> None:
    for side in ("left", "right"):
        for x, y in PLAY_COORDS["defense"][side]:
            assert 330 <= y <= 360, (side, x, y)
            assert _in(x, LANE_X[side]), (side, x, y)


def test_zone_lookup_routes_by_zone_and_card_group() -> None:
    random.seed(7)
    assert zone_play_coords("defense", "left", "bridge_line") in PLAY_COORDS["defense"]["left"]
    assert zone_play_coords("defense", "right", "reactive_spell") in PLAY_COORDS["spell_defense"]["right"]
    assert zone_play_coords("support_behind", "left", "back_support") in PLAY_COORDS["back_support"]["left"]
    assert zone_play_coords("bridge", "right", "bridge_line") in PLAY_COORDS["bridge_line"]["right"]
    assert zone_play_coords("bridge", "left", "bridge_rush") in PLAY_COORDS["bridge_rush"]["left"]
    assert zone_play_coords("chip", "left", "goblin_barrel") in PLAY_COORDS["goblin_barrel"]["left"]
    assert zone_play_coords("spell_tower", "right", "large_spell") in PLAY_COORDS["large_spell"]["right"]
    assert zone_play_coords("none", "left", "bridge_line") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_placement_coords.py -q`
Expected: ImportError `zone_play_coords`.

- [ ] **Step 3: Add the zones and lookup**

Insert into `PLAY_COORDS` (after the `"king_lane"` entry):

```python
    # Defense: in front of our princess tower, in lane, so defenders engage before the
    # tower takes damage. Used for troops and buildings when enemies are on our half.
    "defense": {
        "left": [(115, 340), (100, 352), (130, 348)],
        "right": [(295, 340), (310, 352), (280, 348)],
    },
    # Defensive spells: same band, centred on the lane.
    "spell_defense": {
        "left": [(115, 335)],
        "right": [(295, 335)],
    },
```

Add after `calculate_play_coords`:

```python
_SPELL_GROUPS = {"reactive_spell", "lane_spell", "center_spell", "large_spell", "rocket", "tornado"}
_SELF_TARGETING_GROUPS = {"bridge_rush", "goblin_barrel", "graveyard", "miner", "goblin_drill"} | _SPELL_GROUPS


def zone_play_coords(zone: str, lane: str, card_group: str) -> tuple[int, int] | None:
    """Where to drop a card for a policy zone: the zone's table, or the card's own
    table when the card already aims at the tower (spells, tunnelling, bridge rush)."""
    if zone == "none":
        return None
    if zone == "defense":
        table = "spell_defense" if card_group in _SPELL_GROUPS else "defense"
    elif zone == "support_behind":
        table = "back_support"
    elif zone == "bridge":
        table = card_group if card_group in _SELF_TARGETING_GROUPS else "bridge_line"
    else:  # chip, spell_tower
        table = card_group if card_group in PLAY_COORDS else "lane_spell"
    return calculate_play_coords(table, lane)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_placement_coords.py -q`
Expected: all pass (existing 16 + 2 new).

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files pyclashbot/bot/card_detection.py tests/test_placement_coords.py
git add pyclashbot/bot/card_detection.py tests/test_placement_coords.py
git commit -m "feat(fight): defense placement zones and zone lookup for policy plays"
```

---

### Task 5: Fight loop drives the policy

**Files:**
- Modify: `pyclashbot/bot/fight.py` (`_fight_loop` at ~610-692; add helpers; keep `wait_for_elixir` and `BattleStrategy` in the file for now but unused by `_fight_loop`)
- Test: `tests/test_fight_loop_policy.py`

**Interfaces:**
- Consumes: `read_battle_state`, `BattleState`; `decide`, `choose_slot`, `HandCard`, `PushMemory`, `role_for_group`; `zone_play_coords`, `get_card_group`, `identify_hand_cards`, `check_which_cards_are_available`; existing `check_for_in_battle_with_delay`, `check_if_battle_has_ended`, `check_if_in_battle`, `is_hero_champion_ability_visible`, `trigger_hero_champion_ability`, `HAND_CARDS_COORDS`, `log_play`, `send_emote`.
- Produces: `read_hand(emulator) -> list[HandCard]`, `play_decision(emulator, logger, decision, hand, elapsed, recording_flag, recent) -> HandCard | None`, and the new `_fight_loop` body. Constants `POLICY_TICK_S = 0.5`, `HOLD_TIMEOUT_S = 40.0`, `DETECTION_LOST_LIMIT = 4`.

- [ ] **Step 1: Write the failing tests**

`tests/test_fight_loop_policy.py`:

```python
"""_fight_loop with the policy: read state, decide, tap the chosen slot at the zone."""

from __future__ import annotations

import pytest

from pyclashbot.bot import fight
from pyclashbot.bot.battle_policy import Decision, HandCard
from pyclashbot.bot.battle_state import BattleState
from pyclashbot.bot.coords import HAND_CARDS_COORDS
from pyclashbot.utils.logger import Logger

FULL = {"our_L": 1.0, "our_R": 1.0, "their_L": 1.0, "their_R": 1.0}


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        self.now += 0.5
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class _FakeEmulator:
    def __init__(self) -> None:
        self.clicks: list[tuple[int, int]] = []

    def click(self, x_coord: int, y_coord: int, clicks: int = 1, interval: float = 0.0) -> None:
        self.clicks.append((x_coord, y_coord))

    def screenshot(self):
        return "frame"  # readers are stubbed; the loop only passes it through


@pytest.fixture
def world(monkeypatch):
    emulator, logger = _FakeEmulator(), Logger(timed=False)
    ticks = {"n": 0}
    monkeypatch.setattr(fight, "time", _FakeTime())
    monkeypatch.setattr(fight, "create_default_bridge_iar", lambda _e: None)
    monkeypatch.setattr(fight, "_maybe_start_fight_recording", lambda *a, **k: None)
    monkeypatch.setattr(fight, "stop_fight_capture", lambda: None)
    monkeypatch.setattr(fight, "is_hero_champion_ability_visible", lambda _e: False)
    monkeypatch.setattr(fight, "send_emote", lambda *_a: None)
    monkeypatch.setattr(fight, "random", type("R", (), {"randint": staticmethod(lambda a, b: 0)})())

    def in_battle(_e):
        ticks["n"] += 1
        return ticks["n"] <= 6  # six ticks of battle, then it ends

    monkeypatch.setattr(fight, "check_for_in_battle_with_delay", in_battle)
    monkeypatch.setattr(fight, "check_if_in_battle", in_battle)
    monkeypatch.setattr(fight, "check_if_battle_has_ended", lambda _e: ticks["n"] > 6)
    monkeypatch.setattr(fight, "read_hand", lambda _e: [HandCard(0, "knight", "tank"), HandCard(1, "musketeer", "support")])
    return {"emulator": emulator, "logger": logger, "monkeypatch": monkeypatch}


def _state(elixir: int, enemy_our=(0, 0)) -> BattleState:
    return BattleState(elixir, enemy_our, (0, 0), (0, 0), dict(FULL), 30.0)


def test_attack_taps_the_tank_slot_then_a_bridge_coordinate(world) -> None:
    world["monkeypatch"].setattr(fight, "read_battle_state", lambda _iar, _t: _state(9))
    world["monkeypatch"].setattr(fight, "zone_play_coords", lambda zone, lane, group: (113, 286))

    assert fight._fight_loop(world["emulator"], world["logger"], False) is True

    clicks = world["emulator"].clicks
    assert clicks[0] == HAND_CARDS_COORDS[0]  # knight is the tank
    assert clicks[1] == (113, 286)


def test_hold_makes_no_taps(world) -> None:
    world["monkeypatch"].setattr(fight, "read_battle_state", lambda _iar, _t: _state(3))

    assert fight._fight_loop(world["emulator"], world["logger"], False) is True
    assert world["emulator"].clicks == []


def test_defend_plays_support_when_no_building_in_hand(world) -> None:
    world["monkeypatch"].setattr(fight, "read_battle_state", lambda _iar, _t: _state(2, enemy_our=(0, 90)))
    seen = {}

    def zone(zone_name, lane, group):
        seen.update(zone=zone_name, lane=lane, group=group)
        return (295, 340)

    world["monkeypatch"].setattr(fight, "zone_play_coords", zone)

    fight._fight_loop(world["emulator"], world["logger"], False)

    assert seen == {"zone": "defense", "lane": "right", "group": "back_support"}
    assert world["emulator"].clicks[0] == HAND_CARDS_COORDS[1]  # musketeer, not the tank


def test_play_decision_returns_none_when_no_card_fits(world) -> None:
    decision = Decision("attack", "left", ("building",), 8, "bridge", "test")
    hand = [HandCard(0, "knight", "tank")]
    assert fight.play_decision(world["emulator"], world["logger"], decision, hand, 10.0, False, []) is None
    assert world["emulator"].clicks == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fight_loop_policy.py -q`
Expected: AttributeError `fight has no attribute read_hand` (monkeypatch) / `read_battle_state`.

- [ ] **Step 3: Implement in `fight.py`**

Add imports near the existing ones:

```python
from pyclashbot.bot.battle_policy import Decision, HandCard, PushMemory, choose_slot, decide, role_for_group
from pyclashbot.bot.battle_state import read_battle_state
from pyclashbot.bot.card_detection import get_card_group, identify_hand_cards, zone_play_coords
```

(`check_which_cards_are_available`, `create_default_bridge_iar`, `is_hero_champion_ability_visible`, `trigger_hero_champion_ability` are already imported from `card_detection`.)

Add constants after `ABILITY_TRIGGER_DELAY_S`:

```python
POLICY_TICK_S = 0.5  # how often the policy re-reads the screen while holding
HOLD_TIMEOUT_S = 40.0  # give up holding (assume the elixir bar is unreadable) and play anyway
DETECTION_LOST_LIMIT = 4
```

Add helpers before `_fight_loop`:

```python
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
```

Replace the body of `_fight_loop` (keep the signature) with:

```python
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
                decision = Decision("attack", state.weakest_enemy_lane() or "left", tuple(c.role for c in hand), 0, "bridge", "hold timeout")
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

    stop_fight_capture()
    logger.change_status("Fight complete")
    time.sleep(2.13)
    cards_played = logger.get_cards_played()
    logger.change_status(f"Played ~{cards_played - prev_cards_played} cards this fight")
    return True
```

Then delete the now-unused `BattleStrategy` usage from `_fight_loop` only. Keep `BattleStrategy`, `wait_for_elixir`, `play_a_card`, `select_card_index`, `last_three_cards` in the file if anything else references them (`grep -n "BattleStrategy\|wait_for_elixir\|play_a_card" pyclashbot`); if nothing does, delete them and their now-unused imports so ruff stays clean. `_random_fight_loop` must still work: it uses `play_random_available_card`, not these.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fight_loop_policy.py -q && uv run pytest -q`
Expected: 4 passed, then the whole offline suite green. If `ruff` flags unused imports after deletions, remove them.

- [ ] **Step 5: Commit**

```bash
uvx pre-commit run --files pyclashbot/bot/fight.py tests/test_fight_loop_policy.py
git add pyclashbot/bot/fight.py tests/test_fight_loop_policy.py
git commit -m "feat(fight): policy-driven fight loop replaces elixir-timer and busier-lane play"
```

---

### Task 6: Docs, runner script, live measurement

**Files:**
- Create: `scripts/run_matches.py` (from the scratchpad `run10.py`, unchanged except the module docstring and `SERIAL` read from `argv[3]` defaulting to `127.0.0.1:5565`)
- Modify: `CHANGES.md`, `pyclashbot/bot/AGENTS.md` (mention `battle_state.py`/`battle_policy.py` as leaf modules and the read→decide→act loop), `docs/placement-zones.md` (add `defense`, `spell_defense` rows)

- [ ] **Step 1: Promote the runner**

Copy the scratchpad `run10.py` to `scripts/run_matches.py`; change `SERIAL = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1:5565"`; docstring: `Usage: uv run python scripts/run_matches.py <out_dir> [n_matches] [adb_serial]`.

- [ ] **Step 2: Update docs**

`CHANGES.md`: add a section "New: adaptive battle policy" summarising sections 1 and 3 of the spec in five bullets. `pyclashbot/bot/AGENTS.md`: add one bullet: "`battle_state.py` (frame → `BattleState`) and `battle_policy.py` (`BattleState` + hand → `Decision`) are pure leaf modules; `fight._fight_loop` is read → decide → `play_decision`. Tune thresholds in `battle_policy.py` constants, geometry in `coords.py`." `docs/placement-zones.md`: two table rows.

- [ ] **Step 3: Lint and commit**

```bash
uvx pre-commit run --files scripts/run_matches.py CHANGES.md pyclashbot/bot/AGENTS.md docs/placement-zones.md
git add scripts/run_matches.py CHANGES.md pyclashbot/bot/AGENTS.md docs/placement-zones.md
git commit -m "docs: adaptive battle policy notes and match runner script"
```

- [ ] **Step 4: Live smoke (one match)**

With the BlueStacks instance on the main menu and no other bot running:

```bash
export PATH="/c/Users/HomePC/AppData/Local/Android/Sdk/platform-tools:$PATH"
uv run pytest -x -s --integration --emulator adb --adb-serial 127.0.0.1:5565 -k "1v1_fight"
```

Expected: passes; the bot log (`%APPDATA%\py-clash-bot\logs\<latest>.txt`) shows lines like `defend left: cannon at (115, 340) (enemy on our left)` and `attack right: knight at (300, 284) (even: push right at 8)`, and `Holding (...)` lines between plays. No `Lost battle detection` storms.

- [ ] **Step 5: Ten-match measurement**

```bash
uv run python scripts/run_matches.py <scratch>/run10_policy 10
```

Compare `summary.json` win count against the 2026-09-15 baseline run (record both in `CHANGES.md` under the policy section). Success: more wins than the baseline over ten matches and zero `fight_ok: false`. If worse, first check the logs for `Held too long` and `Holding` durations (thresholds too high) and for defend decisions with no matching card (deck without buildings/support) before touching the policy.
