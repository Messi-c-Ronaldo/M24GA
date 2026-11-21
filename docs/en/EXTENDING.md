# Extending M24GA: registering new game slots and functions

[한국어](../EXTENDING.md) | **English**

The game values a mod can use are only those in [`FIELDS.md`](../FIELDS.md) and [`PROPERTIES.md`](../PROPERTIES.md), and the game functions it can hook are only those in [`FUNCTIONS.md`](../FUNCTIONS.md). If the value or function you want is missing, **do not add a special-purpose function to the core; add one line to a registry (`core/fields.json`, `core/functions.json`).** This document is that procedure. Every command below was actually used (the example is the process of finding a player's asking price).

Preparation: start the game, load a save and run `python -X utf8 loader/cli.py start --now --wait 90`. Commands can be shortened to `m24cli` ([`CLI.md`](CLI.md)).

> **Safety:** the read tools (`explore`, `get`, `find-field`, `classes`, `watch-call`) do not change the game. **Only `watch-write` uses CPU debug registers and the game may crash, so save the game before using it.** Writing game values directly (`api.setField`) is done only after the slot is verified and registered.

## A. Registering a new slot (field)

### 1. Decide which object the value lives on

Pick a target on which the value you want is visible on screen (for example, "asking price on transfer" on a player screen). Target names are `player:<UID>`, `person:<UID>`, `me` (the human manager), `myclub`, `0xaddress`, `fm+0xaddress` (a game global), and appending `/+0x130` follows the pointer in that slot.

```bash
m24cli explore player:2002122126 0x100 0x80    # spread an object out 8 bytes at a time. Pointers get a class name
m24cli classes "TRANSFER|CONTRACT"             # find game class names (works without the game)
m24cli find-global "^GAME_UI$"                  # a global slot that holds a singleton manager object
m24cli find-objects '^BUTTON$' --max 5           # objects of that class (memory search)
m24cli find-refs 0x1d5de7c0                      # slots that point at this object and their owners (follow backwards)
m24cli find-text "Seoul E-Land FC"                 # objects holding a screen text
m24cli ui tree --root 0xaddress --scan 0x400        # screen widgets and the text slots inside them
```

### 2. Find a slot by value (`find-field`)

Give the value shown on screen for **two or more different targets**. One target alone can coincide by chance, so only a slot at the same position and type across several targets can be trusted. A game money amount written as `N억` (Korean billions) is converted to internal units for the search (the screen value is rounded, so the default tolerance is 2%).

```bash
m24cli find-field player:2002122126=1480억 player:19302146=245억 --name player.askingPrice
#   slot common to all targets: +0x1d0 i32 (89100000, 14852187)
#   fields.json draft: "player.askingPrice": {"kind": "player", "off": "0x1d0", ...}
```

- If there are many candidates, add more targets or change the values (after advancing the date, another player) and intersect again.
- If the slot is in another structure inside the object (where a pointer points), `via` (the pointer slots to follow first) appears in the draft.
- For a value not on screen (hidden traits, …), spread objects out with `explore` and compare between players with different values.

### 3. Register it

Add one line to `fields` in `core/fields.json`. Fill in the `TODO`s of the draft.

| Item | Meaning |
|---|---|
| `kind` | Object kind (`player` `team` `club` `human` `staff`). If it is not there, first add it to `kinds` by class name (RTTI) |
| `off`, `via`, `alt` | Position from the start of the object (hex text), pointer slots to follow first, and `{"class": position or null}` when the position differs per subclass. `viaCls` checks the class of the object reached by `via` |
| `type` | `i8` `u8` `i16` `u16` `i32` `u32` `f32` `f64` `ptr` (+`to`) `date` `str` `strref` |
| `unit`, `desc` | Unit (`money` is the internal money unit, KRW = ×1664.7) and meaning (the same as the name on screen) |
| `source` | **The evidence** (which log, which screen value you matched it against) |
| `verified` | `true` if matched against the screen or other values, otherwise `false` |
| `write` | Default `no`. For writing see step 5 |

### 4. Verify it

```bash
python -X utf8 tools/m24.py caps                           # regenerates docs/FIELDS.md
m24cli stop; m24cli start --now --wait 90                  # put core/fields.json into the core again
m24cli get player:2002122126 player.askingPrice            # does it equal the screen?
m24cli get player:19302146 player.askingPrice
python -X utf8 -m unittest tests.test_fields               # format check
```

To compare with the existing value across many players, the surest way is to make a read-only temporary mod that sweeps all players (the method M20 used with 119,449 players: `logs/M24GA/2026-11-08/m20_verify/`).

### 5. When you open writing too (`write: safe`)

Open only slots **verified enough by reading**. If the game also stores that value somewhere else (for example it recomputes CA from the attribute sum), the written value may be overwritten or the save may become inconsistent. Write a writable slot like this:

```json
"write": "safe", "range": [1, 200], "gte": "player.ca", "cap": "write.player.pa", "verified": true
```

- `range` (allowed range), `gte`/`lte` (relation to another field), `cap` (the capability needed; `write.field` if omitted). A slot that is read through a conversion (`map`, e.g. attributes shown 1–20) is written in its stored unit: give it a stored-value `range` and a `unit` that says so.
- The object kind must have `key` and `check` (undo finds the same object again and checks that the object did not change during the write).
- **Live verification procedure:** (1) save the game, (2) write the value once with a temporary mod, (3) confirm on the game screen that it changed, (4) undo with the app's info tab or `m24cli undo <mod id>` and check that the original value comes back. Also advance the date and check whether the value is **reverted or recomputed the next day**.

## B. Registering a new function

### 1. Find the function

The easiest way is to **catch the code that writes that value** (if you have already registered the slot).

```bash
# Save the game! Then:
m24cli watch-write player:2002122126 0x1d0 4 --secs 300 --wait 300     # meanwhile make that value change in the game (advance the date, …)
#   fm+0x3701691 (function fm+0x3700780 +0xf11)  r14 -> db::ACTUAL_PLAYER  r15 -> db::CLUB  rbx -> db::FULL_CONTRACT
```

- The `function fm+0x…` in the result is the **function start (rva)**. `r14 -> db::…` is the class of the object the register pointed at that moment. From the "call path" you can climb up to the caller functions as well.
- It may be caught in more than one place. Choose the **meaningful one** (the function that computes the value) rather than the one caught most.
- To read inside a function use REA (open `fm.exe` and decompile by address) or `python -X utf8 -I tools/fmdis.py ...`.

### 2. Find the arguments and callers (`watch-call`)

```bash
m24cli watch-call fm+0x3700780 --secs 300 --wait 300     # advance the game meanwhile
#   called from: fm+0x372e8db   argument 0 (rcx): SHORTLIST_MANAGER   argument 3 (r9): 2035 ...
```

You learn the class names and integers of the arguments, the return value, the callers and the time taken per call. **How often it is called** matters too (a slow callback on a function called every frame slows the game). It does not use debug registers, so it is safer than `watch-write`.

### 3. Register it

Add it to `functions` in `core/functions.json`.

```json
"player.updateAskingPrice": {
  "rva": "0x3700780",
  "sig": {"off": "0x10", "hex": "01000066440f7fbc24a001000066440f"},
  "args": ["ptr", "ptr", "ptr", "ptr"],
  "argNames": ["SHORTLIST_MANAGER object", "?", "?", "?"],
  "ret": "void", "hook": "observe", "thread": "game",
  "desc": "...", "source": "M21 watch-write, M22 watch-call", "verified": false
}
```

- `rva` must be the **function start** (`tests/test_functions.py` checks it with the exception table).
- `sig` is the 16 bytes at function start + 0x10 **in the `fm.exe` file** (it avoids the first 16 bytes the hook overwrites). On another build it does not match and the core does not hook that function.
- (core 0.38.0) **For a virtual function**, fill `vf: {class, off, index}` (which slot of that class's vtable) with `python -X utf8 tools/func_vf.py fill`. When the build changes and the rva or signature no longer match, the loader finds the vtable by RTTI class name and re-checks the function in the same slot (`loader/funcmap.py`, the 'function registry' section of the build diagnostic report). If the 16 signature bytes occur in several places in the code, the same `fill` adds a longer search byte string `find`. A non-virtual function is found again by searching the code for these bytes (exactly one place + it must be a function start). Check: `tools/func_vf.py check`.
  ```python
  python -X utf8 -c "import sys; sys.path.insert(0,'tools'); import rtti; pe=rtti.PE(rtti.DEFAULT_EXE); o=pe.off(0x3700780+0x10); print(pe.m[o:o+16].hex())"
  ```
- Start `hook` as `observe` (look only). Use **`modify` (changing arguments/return values) only when every argument is understood and `verified: true`**.
- A function the core already hooks is written as `"owner": "core", "event": "..."` (mods use `api.on`).

### 4. Verify it

```bash
python -X utf8 tools/m24.py caps          # docs/FUNCTIONS.md
python -X utf8 -m unittest tests.test_functions
m24cli stop; m24cli start --now --wait 90
m24cli hooks                              # signature check: ok if it matches this build
```

Then hook it with `api.hook('name', { before, after })` in a temporary mod and check `m24cli log <mod id>` and `m24cli hooks` (call counts, errors, time taken) (M22's test mod: `logs/M24GA/2026-11-09/m22_hook/`).

## D. Opening writes with semi-automatic discovery (M78)

Of the work that A and B did by hand, **collecting candidates → verifying → registering** is bundled into commands. What a person does is choose the target and decide the meaning (ko) and the tier.

1. **Designate a test save** (once): with a test save loaded, `cli.py cand testsave add`. Verification writes only happen on this save.
2. **Collect candidates**
   - Static: `python -X utf8 tools/api_scan.py --pylib <capstone folder>` → scalar codes that the property setter (vtable +0x18) accepts and that are not yet in the write registry → `cli.py cand import ~/m24ga_data/api_scan.json`
   - By hand: `cli.py cand add prop <kind> <code>` / `cand add field <kind> <slot> <type> [--via 0x340] [--via-cls db::FULL_CONTRACT]` (a slot found with find-field)
3. **Verify** (`cli.py verify <candidate> <target>` / several at once `verify --all <regex> <target>`)
   - `roundtrip`: write (+1 / flip / +1 day) → read again → undo. It compares **the object's identity and all scalar properties of the same object** before and after the write, and fails if the object changed (the `Ptyp` accident) or another value stays different after undoing. Properties that changed together are recorded as `linked` (candidates for derived values). If the value is empty and cannot be tested, it is skipped and the state is unchanged.
   - `--level day`: write and advance one day (`play`) → pass if kept or drifting from the written value (drift), fail if it went back to the original (reverted, a derived value) → undo
   - `--level save`: write and wait → save in the game (Ctrl+S) → reload the same save → `cli.py verify resume` (waits until the game data tables are ready) → judge → undo
   - `verify --all` stops when it sees signs the object is broken → reload the save and continue.
4. **Register** `cli.py promote <candidate> --tier tested|safe [--ko meaning] [--range min max] [--name field name] [--gte/--lte code]`
   - tested = passed roundtrip; safe = also passed day and save + a range + a meaning. A property goes into `core/properties.json` write, a field into `core/fields.json`, and the docs are regenerated. A blocked code (deny) is refused.
   - After registering, run `python -X utf8 -m unittest discover -s tests` and commit yourself.
- List and results: `cli.py cand list [regex]`, `cand show <candidate>` (`~/m24ga_data/candidates.json`, not put in the repository).
- Functions (calling them) are not opened with this mechanism. The arguments must be understood, so follow procedure B.

## Independent of skin and language (M35–M39)

- Users differ in skin and game language. **Use the game's internals instead of widget ids or screen text**: for data, objects and fields; for actions, registry functions and events (for example continue = `'CONT'` to `ui.continueHandler`, holiday = `ui.holidayStart`, instant result = `'INST'` to `match.clientTacticEvent`).
- The order for finding what a button does internally: check the button's 4-letter id with `find-const` → if it is in the game code, disassemble the function that uses that constant → if not (a skin-only name), while the button is pressed read `watch-call fm+0x1053920` (event sending; the 4-letter code shows as text) or that window's event handler (vtable +0x28). If it is in a protected region (Denuvo) and cannot be read, ask the user to open that screen once and read the window-side handler (M38 holiday).
- A feature that needs a screen to be open writes `"screen": "screen name"` in `capabilities.json` (marked 'screen-dependent' in the docs).

## C. Finishing

1. `python -X utf8 -W error::ResourceWarning -m unittest discover -s tests` — everything passes
2. If the core changed, raise `CORE_VERSION` in `loader/mods.py` (a minor bump if you only added to a registry), and `core` in `core/capabilities.json` with it.
3. In the log (`logs/M24GA/YYYY-MM-DD/MNN_...md`) write **what you verified and how** (screen values, against how many players, live write and undo). Make the registry's `source` point at that log.
4. A trap: delete temporary mods when done (the mod folder, `permissions.json`, `enabled.json`, and the test lines in the write record).
