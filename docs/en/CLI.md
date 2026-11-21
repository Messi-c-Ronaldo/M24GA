# M24GA CLI Reference

[한국어](../CLI.md) | **English**

Every M24GA feature can be used from the command line without the GUI (pywebview). An AI agent can control it directly while developing and testing mods, with no GUI operation.

Written for core **0.44.0**. The channel that controls the loader of a running app is `loader/control.py`.

---

## Running

```bash
# directly
python -X utf8 loader/cli.py <command> [options]

# bat file (in the M24GA folder)
m24cli <command> [options]
```

## Connecting to a running M24GA (the control channel)

The CLI is a separate process that runs once and ends. So **when the app (`start_m24ga.bat`) or `m24cli run` is running, the CLI sends the command to that loader and runs it there**, because the game connection, the mod Python, the mod logs and the write records all live in that loader.

- When the app or `run` starts it opens a channel that is reachable only inside this PC (127.0.0.1, random port) and writes the port and a random token to `~/m24ga_data/control.json`. It deletes it when closed.
- If that file exists and the channel answers, the CLI prints the result as run there. The channel runs only this CLI's commands.
- **If there is no running loader**, it runs inside the CLI process. Then `start`, `stop`, `reload`, `log`, `undo` and `safe-leave` are meaningless because **the loader ends when the command ends** (the CLI shows a note). Start a loader you want to keep running with the app or `m24cli run` (in another terminal).
- Commands that are always done on the spot and not sent to the loader: `validate`, `version`, `run`, `watch` (it asks the loader's `status` instead), `open-mods`, `open-data`.
- The `--json` result contains only that command's output (text printed meanwhile by the loader or mod Python is not mixed in).

**Recommended order for an AI agent:** have the user keep the app running → check the connection with `m24cli status --json` → `start --now --wait 60 --json` (if off) → develop with `reload`/`log`/`report`. It finishes without screen clicking (computer control), so it costs far fewer tokens.

## Global options

| Option | Description |
|---|---|
| `--json` | Can be added to any command. Output is JSON, easy for programs to parse |
| `--help`, `-h` | Help |

---

## Commands

### Status

#### `status`
Loader state: whether it is running, game connection, build, mod summary.
```bash
m24cli status --json
```
Example JSON output:
```json
{
  "phase": "hooked",
  "running": true,
  "build": "FM24 Epic, fm.exe 2026-10-24 build",
  "pid": 12345,
  "game": {"date": "2035-04-25", "save": {"id": 5117219, "nonce": 1}},
  "mods": [{"id": "ai-social-feed", "state": "running", ...}],
  "errors": []
}
```

#### `mods`
The list of found mods and their states. Each mod has a `state`:
- `running`: loaded in the game
- `ready`: ready (waiting for the game)
- `off`: off
- `build`: does not match this game build
- `problem`: cannot be turned on (mod.json problem, etc.)
- `error`: Python error
- `auto_off`: turned off automatically because of repeated errors
- `safe`: not loaded because of safe mode
- `perm`: permission needed

```bash
m24cli mods --json
```

#### `mod <id>`
Details of one mod (including settings).
```bash
m24cli mod ai-social-feed --json
```

---

### Loader control

#### `start [--now] [--wait <seconds>]`
Starts the loader. It waits for the game on a background thread and connects automatically.

| Option | Description |
|---|---|
| `--now` | If the game is already inside a save, build the data tables right away |
| `--wait <seconds>` | Wait until connected to the game. Very useful for an AI |

```bash
# AI agent: start and get the result if connected within 60 seconds
m24cli start --now --wait 60 --json
```

#### `stop`
Stops the loader. It unloads the script and stops the mod Python.
```bash
m24cli stop --json
```

#### `run [--now] [--once] [--check]`
Run in the foreground (stop with Ctrl+C). The same as `host.py`'s console mode.

| Option | Description |
|---|---|
| `--now` | Build the data tables right away |
| `--once` | The loader ends when the game closes once |
| `--check` | Only check the build and end |

---

### Mod management

#### `enable <id>` / `disable <id>`
Turn a mod on or off. If the loader is running, it hot-reloads.
```bash
m24cli enable ai-social-feed --json
m24cli disable ai-social-feed --json
```

#### `install <path>`
Install a `.24mod` file (validate → copy → rescan).
```bash
m24cli install "C:\path\to\my-mod.24mod" --json
```

#### `uninstall <id>`
Delete a mod (moves it to the trash folder). Settings and data remain.
```bash
m24cli uninstall my-mod --json
```

#### `call <id> <function> [args...]`

Calls the mod Python's `ui_<function>(args...)` just as the mod window does with `m24.call('<function>', ...)`. Arguments are JSON (numbers, lists, …) if they parse as JSON, otherwise text. Use it to test a mod without the mod window.

```
m24cli call dynamic-potential state --json
m24cli call dynamic-potential rows up "" 20 --json
```

#### `reload <id>`
Reloads the mod's game-side JS from the current file. The core and data tables stay as they are (hot reload).
```bash
# after editing mod.js
m24cli reload my-mod --json
```

#### `grant <id>`
Allows the risky capabilities the mod needs (pc, raw, hook, write) and turns it on.
```bash
m24cli grant my-mod --json
```

#### `rescan`
Rescans the mods folder. If the loader is running, Python and the script follow the changed mods.
```bash
m24cli rescan --json
```

---

### Settings

#### `settings <id>`
Shows the mod settings. In JSON mode `specs` (settings item definitions) and `values` (current values) appear.
```bash
m24cli settings ai-social-feed --json
```

#### `set <id> <key> <value>`
Changes a mod setting. The value is type-converted automatically (true/false → bool, number → int/float, otherwise → string).
```bash
m24cli set ai-social-feed api.model gpt-4o --json
m24cli set ai-social-feed api.key sk-xxxxx --json
m24cli set my-mod count 10 --json
m24cli set my-mod enabled true --json
```

---

### Logs and reports

#### `log <id> [--since <number>]`
The mod's recent log. With `--since` only entries after that number appear.
```bash
m24cli log ai-social-feed --json
m24cli log ai-social-feed --since 42 --json
```

#### `log-clear <id>`
Clears the mod log.

#### `report <id>`
**Report to hand to an AI**: collects the mod state, why it was turned off automatically, the validate result and the recent log in one go. When something goes wrong, paste this output to an AI.
```bash
m24cli report ai-social-feed
```

#### `build-report`
**Game build diagnostic report**: when the loader meets a game build it does not know (for example the Steam version), it tells you what differs. It contains file size, SHA-256, PE build time, version text, and expected/actual values for each signature and vtable slot, with personal paths removed. It can be made after attaching to the game once, and when the build does not match the loader saves it automatically to `~/m24ga_data/build_report.txt`. The app home screen's **Copy build diagnostic report** button gives the same text.
(core 0.38.0) The 'function registry' section: shows whether the registered functions' signatures match this build and, if not, whether they were found again through the class vtable slot (`vf`) or a signature search. The loader loads functions found again at their new addresses.
```bash
m24cli build-report
```

#### `writes <id>`
The mod's game-value write record.

#### `undo <id>`
Undoes the values the mod changed in the current save.

---

### Safe mode

#### `safe`
Check the safe-mode state. If the previous game ended abnormally, safe mode is on.

#### `safe-leave`
Ends safe mode and loads the mods that were left on.

---

### Investigating the game (core 0.9.0)

#### `explore <target> [start slot] [size]`
Spreads a running game's object out 8 bytes at a time. It follows pointers and attaches the **class name** (RTTI), and shows game text slots as text and game date slots as dates. Slot and size are hex (default 0, 0x200, max 0x4000). Read-only.

| Target | Meaning |
|---|---|
| `0x12345678` | An address |
| `player:<uid>` | A player object (`db::ACTUAL_PLAYER`) |
| `person:<uid>` | That player's person data object (`personOf`, player +0x278) |
| `me` | My manager (`db::HUMAN_NON_PLAYER`) |
| `myclub` | My club (`db::CLUB`) |
| `/+0x130` appended | Follow the pointer in that slot (can repeat: `player:123/+0x130/+0x30`) |

```bash
m24cli explore player:2002122126 0x100 0x80
#   +0x130  00000000de960c00  -> db::TEAM
#   +0x150  07f37cb107f300ba  i32 ...  dates 2035-07-05, 2035-06-26
m24cli explore "player:2002122126/+0x130" 0 0x40 --json
```

#### `get <target> <field> [field...]` (core 0.10.0)
Reads slots of the field registry ([`FIELDS.md`](../FIELDS.md)) by name. Targets are the same as `explore`. If a field name ends in `.`, it reads every field starting with that name.
```bash
m24cli get player:2002122126 player.name player.ca player.pa player.askingPrice
m24cli get player:2002122126 player.season.league.
m24cli get myclub club.name
```

#### `fields [regex]` (core 0.10.0)
The field registry list (name, type, whether writable, meaning). Works even when the game is off.

`explore` attaches field names to registered slots like `[player.ca, player.pa(+2)]` (`(+2)` is 2 bytes later inside that 8-byte slot).

The 54 player attributes: `get player:<uid> player.attr.`.

#### `props <target> [regex] [--empty]` (core 0.36.0)
All game property code values (registry `core/properties.json`, docs [PROPERTIES.md](../PROPERTIES.md)). Targets: `me` · `myteam` · `myclub` · `myjob` (my manager's contract) · person reference `p123`/`s45` · `team:<number>` · `comp:<number>` · `contract:p123`/`contract:s45`/`contract:me` · `player:<uid>` · `0xaddress`.
```bash
python -X utf8 loader/cli.py props myclub "^(Ccba|Ctfc|Cwwb)$"   # balance, transfer budget, wage budget
python -X utf8 loader/cli.py props player:2002117436 "^P(ced|dob|cwg)$"
```
If `~/m24ga_data/prop_names.tsv` (code, English, game language, display format, category) exists, names are shown too (e.g. `Crossing [attribute · attribute_label]`). This table is game text, so it is not in the repository. **Each user makes it from their own game files with `python -X utf8 tools/prop_names.py --pylib <zstandard folder>`** (1,655 entries, 2–3 minutes the first time, language with `--lang`). About 900 of the registry's 2,297 codes get a name (the rest are internal codes with no name on the game screen).

#### `prop-find <target> <value>` (core 0.36.0)
Finds which property code holds a value shown on screen (number, text, date `2038-06-30`), including inside records and lists. For checking codes whose meaning you do not know.

#### `actions [regex]` (M62)
The list of 198 game actions (commands): 4-letter id, class, whether in a protected region, the context keys the check function reads. Works even when the game is off. It also shows execution events. Reading and running the commands available for each target is done with the mod API `api.actionsFor` / `api.action` (core 0.41.0) ([ACTIONS.md](../ACTIONS.md)).

#### `cand` / `verify` / `promote` (M78, semi-automatic API discovery)
Collects write candidates, verifies them automatically on a test save and registers them. Procedure: [`EXTENDING.md`](EXTENDING.md) section D.
```bash
m24cli cand testsave add                                  # make the current save the test save (verification writes happen only here)
m24cli cand import ~/m24ga_data/api_scan.json             # the tools/api_scan.py result
m24cli cand add prop contract Cabo                        # by hand
m24cli verify prop:contract:Cabo contract:p45806          # roundtrip
m24cli verify --all "^prop:contract:" contract:p45806     # several
m24cli verify prop:contract:Cabo contract:p45806 --level day
m24cli verify prop:contract:Cabo contract:p45806 --level save   # -> save and reload -> verify resume
m24cli promote prop:contract:Cabo --tier tested
```
`vsnap <target>` (identity + all scalar properties) and `vset <target> prop|field …` (read/write with no registry check; writes only on the test save) are the low-level commands verify uses.

#### `prop-info [regex] [--writable]` (core 0.36.0, write marks 0.42.0)
The property registry list (code, value type, the object kinds that answer, the verified meaning). Works even when the game is off.
Each code gets a write tier: `[write safe range]`, `[write tested]`, `[write blocked]`. With `--writable` only the codes you can write with `api.setProp` are shown (writing is only from mods: capability `write.prop`).

Tip for matching screen values and codes: `ui text` shows a 4-letter code per widget, and the code of a number widget is usually the **property code** that asks for that value (e.g. the player profile `ATTRIBUTE_LABEL Pcro` = crossing).

#### `find-field <target>=<value> [<target>=<value> ...]` (M21)
Finds a slot by known values. It sweeps the target object (0x800 bytes from the start) and where its pointers point (0x400 bytes each). **If you give several targets, only the slot at the same position and type in all of them** is kept, and a draft line for `fields.json` is shown. Read-only.

| Value | Meaning |
|---|---|
| `89100000` | That value (`--tol 0.01` for ±1%) |
| `100..200` | A range |
| `1480억` | Money on the game screen (KRW ÷ 1664.7 = internal unit, default tolerance 2%: the on-screen value is rounded) |

Options: `--type i32,f32` (default: i32·u32·f32·f64 for big values, i8–u16 too for small ones), `--size 0x1000`, `--shallow` (do not follow pointers), `--name player.askingPrice` (draft name).
```bash
m24cli find-field player:2002122126=1480억 player:19302146=245억 --name player.askingPrice
#   slot common to all targets: +0x1d0 i32 (89100000, 14852187)
#   "player.askingPrice": {"kind": "player", "off": "0x1d0", "type": "i32", ...}
```

#### `find-bytes <pattern> [--max 40] [--secs 20] [--align N] [--ctx 16] [--owner] [--module]` (core 0.32.0)

Finds a byte pattern in the game heap (writable regions). For each hit it shows the surrounding bytes; with `--owner` the RTTI object (the owner) within the preceding 0x800, and with `--module` it also sweeps fm.exe's global regions.

```
m24cli find-bytes 0b ?? 0f              # hex, ?? = any byte
m24cli find-bytes --u8 0 11 15 19 4 8  # list values (--u8 --i8 --u16 --i16 --u32 --i32 --u64 --i64 --f32 --f64)
m24cli find-bytes --i32 11 ? 15 --align 4   # ? = any value of that size
```

It was used to find the tactical style table (`styles.xml`) in memory (three u8 at a time).

#### `find-const <4 letters>` (M37)

Finds where a 4-letter constant (widget id, event code) is used in the running `fm.exe` module (including code). Use it to check **whether the game code uses that name directly**: 0 places means a name only the skin file knows, so a skin can change it (`GCNT`, `MDSB`, `ctnu` are 0 places; `INST` is 2). Part of `fm.exe` on disk is encrypted, so this is more accurate than a file search. `watch-call` results also show integer arguments that look like 4 letters as text, like `'CONT'`.

#### `watch-write <target> <slot> [size]` (M21)
Puts a **hardware write watch** on one slot (1, 2, 4 or 8 bytes) to find the game code that writes to it. Each time it is caught it collects the code location (`fm+0x…` and the function start), the call path, the class (RTTI) of the object the registers pointed at, and the value written. After `--max` catches (default 30) or `--secs` seconds (default 60, max 600) it **releases itself.** One watch at a time.

- `--wait seconds`: waits meanwhile and then shows the result (it waits on the CLI side, so you can use `watch-write show` and `stop` from another window). Without it, it returns at once and you look with `watch-write show`. `watch-write stop` releases now.
- `--rw`: catches reads too (it can be caught very often). **Do not use it on a frequently read slot (engine tables, …)**: `--max` fills instantly across threads. Before core 0.29.1 the game crashed on a late watch exception here. From 0.29.1 the handler is not removed until late exceptions stop for 3 seconds, and they are swallowed (`late` counts them). Stop the loader after `excSet` in the result is false.
- The target may also be a **game global slot** such as `fm+0x631d5bc` (the same for `explore` and `get`).
- **Warning:** it uses CPU debug registers. It applies only to game threads that existed when you set it (threads created later are not caught). The game may crash, so **save the game first**.
```bash
m24cli watch-write fm+0x631d5bc 0 4 --secs 120 --wait 120     # advance a day in the game meanwhile -> the code that writes the date
m24cli watch-write player:2002122126 0x1d0 4 --secs 300 --wait 300
```
Continue with the function you find in REA (open `fm.exe` → decompile by address) or `tools/fmdis.py`.

#### `engine dump|apply|restore` (core 0.30.0, DynamicME)
Reads and changes the match-engine tables (selection weights, physics, momentum, ratings) **while the game is running, without a restart**. The game reads the memory tables as they are at match and selection time, so the change is reflected from the next selection/match. It does not write while the game is running (adjust before a match).
```bash
m24cli engine dump physics --out physics.json     # weights|physics|momentum|ratings|styles, memory as it is (read only)
m24cli engine apply "D:\downloads\(engine name)" --dry   # engine pack (simatch folder) preview: what it writes where, warnings
m24cli engine apply "D:\downloads\(engine name)"         # straight into game memory
m24cli engine restore                              # back to the original values of the game install folder's simatch.fmf
```
- It writes only to existing slots (no allocation). If the pack removed an item of a newer version, it puts a valid pack item into the slot the game uses (weights, physics) or keeps the game from choosing the removed item (ratings).
- It warns about keys and region names the game does not know, delays that are not multiples of 0.25 seconds, and fractional rotation values. Tables of a different shape (two QME ones) cannot be put in yet.
- Conversion and planning are in `pylib/m24engine.py`. Memory is not stored in the save (the original returns when the game restarts).

#### `find-global <class regex> [max]` (M24)
Among fm.exe's global slots, finds those that point at an object of that class. Use it to find where a manager object that exists only once in the game (a singleton) is. It reads 1 MB at a time and stops at an 8-second budget (shown in the result).
```bash
m24cli find-global "^(GAME_UI|GAME_SCREEN_MANAGER|SCREEN_CLIENT_MANAGER)$"
#   fm+0x63659c0 -> 0x1d2a82c0  GAME_UI
#   fm+0x63635b8 -> 0x45972c0   SCREEN_CLIENT_MANAGER
```

#### `find-objects <class regex> [--max 40] [--secs 20]` (M24)
Finds objects of that class in game memory (searches the vtable value at the object start with `Memory.scanSync`, 2.7 GB in 5–10 seconds). If more than 24 vtables match the regex it asks you to narrow it. Spread the addresses found with `explore`.
```bash
m24cli find-objects '^BUTTON$' --max 12
m24cli explore 0xbcb1f8d0 0 0x400
```

#### `find-refs <target> [--max 40] [--secs 20] [--back 0x800]` (M25)
Finds the **slots that point at** that address in the heap and fm.exe globals (follow backwards: who holds this object). For each slot it finds the nearest RTTI object within the preceding `--back` bytes and shows it as "class +slot". Target names are the same as `explore`.
```bash
m24cli find-refs 0x1d5de7c0          # what holds GAME_SCREEN_CLIENT
#   0x15579f18  SCREEN_CLIENT_MANAGER::INTERNAL_DATA +0x18 ...   (screen list)
#   0x365ad28   sitoolkit::WIDGET +0x48 ...                       (each widget's own screen)
```

#### `find-text <screen text> [--max 6] [--secs 40]` (M25)
Finds text visible on screen (UTF-8) in memory and climbs, following the slot that points at it and the slot that points at that slot (the string handle), up to the **owner object**. A game string is `handle → pointer → {u32 length, UTF-8}`. Traces of deleted widgets are caught too, so check that there is a parent (+0x10). Text with mixed formatting (large news titles) may not be caught.

#### `ui text` / `ui tree` (M25, the AI player's "eyes")
Reads **the current game screen as text.** A command that lets an AI know the screen without a screenshot. Read-only (100–500 ms).
- `ui text`: only **visible** widgets that have text, in screen order. Each line is `text  [class id address @centre x,y]`; things that need scrolling to be seen get `off-screen`. A checkbox has `☑`/`☐` in front, widgets inside popups and dialogs get `popup`, and when a popup is up the last line says `popup open` (M27).
- `ui tree`: the whole visible widget tree (class, id, child count, flags, position/size, text). With `--all` hidden ones too (`hidden`).
- `--json`: `checked` (checkbox) and `modal` (inside a popup) per node, and `modal` (is a popup up) in the result.
- Options: `--root 0xaddress` (only below that widget), `--depth 40`, `--max 3000`, `--scan 0x400` (for investigation: all text slots inside the widget body), `--json`.
```bash
m24cli ui text
#   Inbox  [TEXT sect 0xc501a790 @319,33]
#   35/7/2  [TEXT dtam 0xc501b410 @...]
#   Al-Ittihad offer for Vinicius Junior  [TEXT titl 0xffbfb720 @...]
#   Barcelona  [TEAM_BUTTON Ttea 0x10b121800 @1684,591]
#   114  [LEAGUE_POINTS_TEXT LOpo 0xf0eaf930 @1849,591]
```
How it reads (M25): `fm+0x63635b8` (SCREEN_CLIENT_MANAGER) → `+0x68` → `+0x18` screen list → `GAME_SCREEN_CLIENT` → `+0x58` root container → the child array (`+0x100`/`+0x108`). A widget's `+0x5c` is the 4-letter id, `+0x60` x·y·width·height (floats, game window pixels), `+0x78` flags (0x2 = visible, children are hidden when the parent is hidden; for a checkbox 0x10 = checked). Popups hang under the root's `modl` container → the `MODAL_SHEET` branch. Text is the line list at `+0x98` of the `MULTI_LINE_STRING` inside the widget (or the `CLICKABLE_TEXT` that inherits it). Widgets with only icons or pictures, and some widgets drawn from data on the fly (team names in recent results, etc.), show no text.

Things to know (M27, checked against squad, tactics and popups):
- In a long list **only the visible rows exist as widgets.** When you scroll, existing row widgets move and new rows appear. To see the whole list, read several times while scrolling.
- **Right after** opening a screen the layout is not finished, so positions may be off or text missing. Wait a moment or read twice and compare.
- In a table, a cell widget's id equals its column heading's (`COLUMN_HEADING`) id (e.g. the name cell and the "Name" heading are both `Pnms`). Grouping by the same y gives a row.

#### `ui state [--watch seconds]` (M30, the AI player's "waiting")
A one-line game progress state: `2035-07-02 Mon 10:30  button:Continue [processing] [popup] [mail to answer]  screen:Inbox`. The date comes from the global `fm+0x631d5bc` (upper 16 bits year, lower 9 bits day of year, the bits above that are the time — rising by 0x200 while processing), the button from the top-right `GCNT` (the continue family) or `MDSB` (reply needed), and "processing" is judged from the value at `+0xc0` of the game's `CONTINUE_MANAGER` (global `fm+0x6364ea0`) (independent of skin, core 0.12.1; it is processing even while the processing screen `GAME_PROCESSING_PANEL_CONTAINER` is shown). `--watch seconds` prints a line at every change (polled on the CLI side every 0.25 seconds). With `--json` also `raw` (the raw date value).

#### `play --days N [--manual] [--steps 400] [--quiet] [--json]` (M32, automatic advancing for tests)
A command that **advances the game N days when testing a mod.** It runs on judgement-free default rules (for test saves).
- **Default = holiday (M38, independent of skin and mail kind):** go on holiday with `act holiday --until target date`. During the holiday the assistant manager handles matches, mail and admin, and you return on the target date. If the holiday ends midway (a confirmation dialog, …) it closes the dialog with `Yes` and goes again (up to 4 times). If it cannot finish with a holiday it falls back to the step-by-step advancing below. Live: 8/19 → 8/24 in 134 s, including league matches.
- `--manual`: do not use the holiday; only step-by-step advancing (screen rules; answer mail yourself and handle matchdays; for testing mail and meeting handling).
- Mail to answer → open it (`MDSB`); `no` if the title contains reporter, press conference, offer made, offer, wants a loan, otherwise `yes` (`act reply --yes --all`; the opposite kind if that kind of button is absent). For multi-offer mail it goes through only the lines not yet handled.
- Confirmation dialog → `Yes`. Player meeting → the first answer. The next button of meetings (`nxbt`/`endB`) is treated like continue.
- **Matchday**: on the team selection screen, `Quick pick` [`askp`] (automatic, excluding injured players) → `Instant result`. If the skin has an `Instant result` [`INST`] button it uses it, **otherwise `act instant`** (a game-internal event, independent of skin). The result window is closed by `act dialog` with close (`clos`). If you end up watching the match (the live match screen), only when the clock has stopped it presses `IMBu` (the pause/resume toggle) once.
- **Judging "processing" (independent of skin):** the core reads it from `CONTINUE_MANAGER` (`busy` of `ui state --json`, and `seq`, which rises on every state change). `act continue` does not press while processing either (pressing would pause).
- While processing it does not press and waits. Stop conditions: the target date is reached (success, exit code 0) / **an unfamiliar screen** (no continue button) / the same state repeated more than 8 times / the same mail 6 times / the step limit. When it stops it shows the current state and the screen text.
- The waiting loop runs on the CLI side. Every action goes to `act_log.jsonl`.
```bash
m24cli play --days 3
#   matchday: quick pick
#   continue (instant result) 1.7 s -> 2035-07-18 Wed 12:00 submit squad
#   ...
#   target date reached: 2035-07-18 -> 2035-07-21 (154 s)
```

#### Language (M39)
- The danger-button protection (`--yes`) and the judgement of transfer/contract mail use Korean and English words. If the game is played in another language it cannot recognise the words, so the core guesses the language from screen text (`lang` of `ui state --json`: ko / en / unknown) and **for an unknown language treats short action buttons and every mail answer as dangerous** (it presses only with `--yes`). `play` already answers with `--yes`, so it works as it is.

#### `act holiday [--days N | --until YYYY-MM-DD] [--accept-offers]` (M38, holiday — independent of skin)
- Goes on holiday (default 7 days). It does not use the screen; it calls, on the screen thread, the function that the holiday window (`GO_ON_HOLIDAY_DIALOG`)'s `Go on holiday` calls (registry `ui.holidayStart`, fm+0x7a19a50). The game sends a `'GOHL'` message to the server and starts the holiday.
- Options: the same as the window's defaults — **reject all offers + use the current tactics + return on the date** (bits `0x242`). `--accept-offers` accepts only offers that meet the asking amount (`0x4`). Manager job applications are not supported.
- During a holiday `kind` of `ui state` is `-6` and `busy` is true. `act continue` is not done then (the continue button cancels the holiday).
- It does not run while processing or with a popup up.

#### `act instant [--index N]` (M33, instant result — independent of skin)
**On the team selection screen** on a matchday, produces the result without watching the match. It works even without an `Instant result` button as in the default skin.
- How it works: the skin's `Instant result` (id `INST`) button ends up sending an `'INST'` event to the event handler of `CLIENT_TACTIC` (the pre-match tactic object) (sub-vtable +0x28 of the +0x38 part = registry `match.clientTacticEvent`, fm+0x223200). That handler calls the instant-result function (fm+0x277b10, called only on this path). `act instant` finds `CLIENT_TACTIC` in memory and sends the same event on the screen thread (only when the handler address matches the registry signature).
- `CLIENT_TACTIC` exists **only while on the pre-match team selection screen** (0 during a live match or half time). If there is none it fails with `none`. The search takes 5–10 seconds.
- Live (M33, original skin): a 7/24 Marseille friendly → straight from 12:00 to 13:45, the result window "1 - 2" (scorers and ratings).

#### `ui mail` / `act reply [ybut|xbut|yes|no|button text] [--yes]` (M31, reading and answering mail)
- `ui mail`: the mail open in the inbox as a structure — title (`nwhd`), sender (`snob`/`sjob`), body (`etxt`), detail text (amounts, conditions …), buttons inside the mail (`ybut` confirm kinds, `xbut` reject/cancel kinds, the `Tasks` delegation menu, links), whether **an answer is needed**, whether it is **transfer/contract related**, and the mail list on the left (time, sender, title). The tool buttons above the list are left out.
- `act reply`: presses **only buttons inside the open mail** (default `ybut`). If the mail title/body contains transfer, contract, offer, loan, signing, sale, release, sacking, bid or negotiation words (`MAIL_DANGER` in `core.js`), `--yes` is needed. It judges by the mail content instead of the button-text danger rule (`ACT_DANGER`).
- The answer button kind (`kind`) is decided by id (`ybut`/`xbut`) or text: `yes` = confirm, accept, accept offer, attend; `no` = reject, cancel, reject offer. A transfer offer mail has `Accept offer` [`set `] / `Propose terms` [`sgtm`] / `Reject offer` [`disc`], so `act reply yes|no` is convenient.
- Order for mail to answer: `[mail to answer]` in `ui state` → `act continue` (in the reply-needed state it opens the mail to answer, M37) → `ui mail` → `act reply yes|no [--yes]` → (if a confirmation dialog appears) `act dialog yes|no`.
- `act dialog [yes|no|button text] [--yes]`: Yes/No of the **popup (confirmation dialog)** that is up. It returns the question (`ques`) too. Example: "Do you want to reject the offer for Stefan Hitzsperger?" → `Yes` [`yes `] / `No` [`no  `] (option radio buttons with `act click`).
- For screens like a player meeting (one-to-one talk): the question `qusl`, answer buttons `answ` (several, with the `gptl` tone above: agree, promise, persuade, insist, threaten), the reaction `ReaT` (concerned → encouraged …). Answer with `act click <answ address>`, and at the end `act continue` on the top-right `nxbt` ("Summary" → "Leave the meeting").
- Not yet possible: **picking and opening a specific mail** in the left list (the line `NEWS_ITEM_LIST_WIDGET` is not a button and the click path has not been found). Unread mail opens in order with `act continue` ("Next unread").
```bash
m24cli ui mail
#   ■ Vinci agrees terms with AC Milan
#     sender: Jonas Bolt (Football Director)
#     ... buttons: Extra amount, Tasks, Confirm [ybut], Postpone, Cancel [xbut] ...
#     (answer needed, transfer/contract related (act reply needs --yes))
m24cli act reply ybut --yes
```

#### `act continue` / `act click <target>` (M28, the AI player's "hands")
**Operates the game screen directly.** It does not click mouse coordinates; it runs the game's internal button action **on the screen thread (`onFrameEnd`, `fm+0x1049430`)**, so it behaves the same even when the window is covered or the resolution differs.
- `act continue`: presses the top-right button (`GCNT`: continue/social feed/inbox/next unread = the space bar) to advance. On a screen without that button it calls the registry function `ui.continueGlobal` (the global `CONT` event, **only when the signature matches**).
  - **Independent of skin (M37, core 0.13.0):** it does not press the button widget but sends a `'CONT'` event to the game's `CONTINUE_MANAGER` (global `fm+0x6364ea0`) (`ui.continueHandler` = the game's `handle_continue_game_action`). The game does the right thing for the current kind: advance / next unread / inbox / **open the mail to answer** (reply needed). The button ids `GCNT`/`MDSB` are names the skin file decided (not in the game code), so they are used only for text display. Two days of automatic advancing were confirmed in a test imitating a skin that changed the ids.
  - The kind is `kind`/`kindName` of `ui state --json` (`ui.continueKind`): `-1` continue (continue, social feed, key fixtures, …), `-8` nextUnread, `-19` inbox, `-14` needReply, `-3`/`-4` processing.
  - **When it does not do it:** with a popup up, while the game is processing (`busy`), on a **screen with no continue button** (during a meeting question, a match … `noButton`; use `--force` to do it anyway). On step screens (meeting `nxbt`, pre-match `IMBu`) it presses the next button.
- `act continue --wait [seconds]` (M30, default 60 seconds): after pressing continue, waits **until the game waits for input again.** Stopped = the processing screen is not visible and the state (date/time, top-right button, popup, mail to answer, screen title) has stayed the same for 1 second after changing. The result is the before/after state and what to do next (mail to answer → `act click MDSB`, popup → `ui text`). With `--json` also the coarse steps (`steps`) and whether the processing screen was seen. The waiting loop runs on the CLI side (it does not hold the app channel).
  - Live (M30): `Continue` 10:30 → processing 14 s → 12:30 `Next unread`. `Next unread` → 1.6 s → `Reply needed`.
- `act click <target> [--index N] [--partial] [--yes] [--behind]`: finds a visible button widget and clicks it.
  - Target: `0xaddress` | a 4-letter `id` (e.g. `TeSq`, `GCNT`, `MDSB`, `FiBn`, `anLB`) | text visible on screen (e.g. `Squad`, `Tactics`, `Conditions`, `Analysis`).
  - If you give a text widget's address it presses the `BUTTON` containing that widget (itself or an ancestor). **It does not look toward children** (if it is not a button and not inside a button it fails).
  - It calls the virtual click handler `vtable[+0x140](widget, event)` that every `BUTTON` and subclass (`CHECK_BOX`, `RADIO_BUTTON`, `POPUP_BUTTON`, `sitoolkit::TOGGLE_BUTTON`, `sitoolkit::WIDGET_POPUP_BUTTON`, `SIDEBAR_LABEL`, `ICON_BUTTON`, …) inherits.
  - **Safeguards (M29):**
    - The text must **match exactly.** A button that matches only partly shows only candidates and is not pressed → `--partial`.
    - If **several buttons match**, it does not press and shows the candidate list → pick with `--index N`.
    - **When a popup is up, only buttons inside the popup** are pressed. If you must press outside, as when closing a popup with the button that opened it, use `--behind`.
    - **Short button text** that can change the save (15 characters or fewer containing offer, contract, accept, reject, sack, release, sell, loan, sign, bid … — `ACT_DANGER` in `core.js`) is pressed only with `--yes`. Long text (news titles) is excluded because it only opens something to read.
    - It presses only buttons whose **own and all parents are visible**.
- Every `act` is recorded as one line in `~/m24ga_data/act_log.jsonl` (time, command, target, success/failure, the text of the pressed button, whether `--yes`). An AI can see later what it pressed.
- With `--json`, even on failure it returns a result with the candidates (`matches`), `needConfirm`, `needReply` (exit code 1).
- **Caution:** **save the game first** before any operation that advances the game or changes its state.
```bash
m24cli act click Squad
#   clicked: SIDEBAR_LABEL TeSq 0x10ae27f10 "Squad"
m24cli act click FiBn
#   clicked: sitoolkit::WIDGET_POPUP_BUTTON FiBn 0x117efb160 "Conditions"
m24cli act click anLB
#   clicked: CHECK_BOX anLB 0xe5c21560 "Analysis" -> ☑
m24cli act continue
#   ran continue (button: Social feed)
m24cli act click Inbox
#   error: there are 2 'Inbox' buttons. Pick one with --index (nothing was pressed)
#     #0 Inbox  [MENUBAR_ICON_BUTTON Pibx 0xe3bd6c20]
#     #1 Inbox  [SIDEBAR_LABEL Pibx 0x10e390110]
m24cli act continue        # when there is mail to answer
#   ran continue (reply needed)   <- opens the mail to answer (not refused since M37)
```

#### `functions [regex]` (core 0.11.0)
The function registry list (location, arguments → return, hooking observe/modify/core-only). Works even when the game is off. The detailed table is in [`FUNCTIONS.md`](../FUNCTIONS.md).

#### `hooks` (core 0.11.0)
The hooks currently attached (mods, call counts, errors, time taken per function) and the **signature check** result of registry functions (a function that differs from this build is not hooked).

#### `watch-call <function name | fm+0xaddress>` (M22)
Watches one function for a moment and collects **the identity of the first 4 arguments** (RTTI class, integers, addresses), the return value and the callers. Use it before registering a function whose arguments you do not understand. It releases itself after `--max` calls (300) or `--secs` seconds (30, max 600). `--wait` waits on the CLI side, `show`/`stop`. It does not use debug registers (it is the Interceptor the core normally uses). When you give an address it must be a **function start** (the "function fm+0x…" of a `watch-write` result).
```bash
m24cli watch-call player.updateAskingPrice --secs 300 --wait 300   # advance the game meanwhile
#   2 calls, called from fm+0x372e8db, argument 0 (rcx): SHORTLIST_MANAGER ×2 ...
```

#### `classes <regex>`
Searches fm.exe's class names (10,000+). It also shows the vtable address (RVA) and inherited classes. **It works even when the game is off** (the first time `tools/rtti.py` builds the table and saves it in `~/m24ga_data/rtti/`, about 6 seconds).
```bash
m24cli classes "TRANSFER_VALUE|ASKING_PRICE"
```

### Other

#### `validate <path>`
Validate a mod (the same as `tools/m24.py validate`).
```bash
m24cli validate mods/my-mod --json
```

#### `watch [--interval <seconds>] [--until <phase>]`
Prints the state periodically as one JSON line. The AI does not need to poll.

| Option | Description |
|---|---|
| `--interval <seconds>` | Output interval (default 5 seconds) |
| `--until <phase>` | Stop when this phase is reached (`hooked`, `error`, `unsupported`, …) |

```bash
# watch until connected to the game
m24cli watch --until hooked
```

Example output (one line each):
```json
{"time": "16:30:05", "phase": "waiting", "running": true, "build": null, "game": {}, "mods_loaded": []}
{"time": "16:30:10", "phase": "attaching", "running": true, "build": null, "game": {}, "mods_loaded": []}
{"time": "16:30:35", "phase": "hooked", "running": true, "build": "FM24 Epic, fm.exe 2026-10-24 build", "game": {"date": "2035-04-25"}, "mods_loaded": ["ai-social-feed"]}
```

#### `version`
The core version.

#### `open-mods` / `open-data <id>`
Opens a folder in the file explorer. With `--json` it prints only the path.

---

## AI agent workflow

### Mod development cycle

```bash
# 1. create a skeleton
python -X utf8 tools/m24.py new my-mod --python --ui

# 2. write code (the AI edits files)

# 3. validate
python -X utf8 loader/cli.py validate mods/my-mod --json

# 4. start the loader & wait for the game connection
python -X utf8 loader/cli.py start --now --wait 60 --json

# 5. hot reload after changing code
python -X utf8 loader/cli.py reload my-mod --json

# 6. check the log
python -X utf8 loader/cli.py log my-mod --json

# 7. if there is a problem, the report
python -X utf8 loader/cli.py report my-mod
```

### Changing settings

```bash
python -X utf8 loader/cli.py settings ai-social-feed --json
python -X utf8 loader/cli.py set ai-social-feed api.key sk-xxx --json
```

### Watching the state

```bash
# wait until attached to the game (stop with Ctrl+C)
python -X utf8 loader/cli.py watch --until hooked
```

---

## Differences from the GUI (`app.py`)

The CLI calls the same `host.py`/`mods.py` functions as the `Api` class of `app.py` (inside the app through the channel above when the app is running). There are only **two feature differences**:

1. **File picker** — in the GUI you pick a `.24mod` in a dialog, but in the CLI you give the path directly (`install <path>`)
2. **Mod window** — the mod UI inside the iframe that only the GUI shows is not rendered by the CLI

Otherwise they are the same. When using only the CLI, pywebview is not needed (frida is).
