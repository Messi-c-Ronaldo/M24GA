# M24GA

[한국어](README.md) | **English**

An open-source mod loader for Football Manager 2024 (Epic build). A mod is a single `.24mod` file, and you switch it on/off and configure it from the app.

> **Beta notes (0.44.1 = core version)**
> - Verified on **FM24 24.4.2 (build of 2025-04-16), Epic and Steam**. If the game build does not match, the loader injects nothing and stops, so the game stays safe.
> - **The Steam version of 24.4.2 is supported since 0.42.1** (confirmed working by a Steam user). Steam and Epic are the same game code with different packaging. If you still see "Unsupported game version", press **Copy build diagnostic report** on the app's home screen and paste it into an Issue (it contains only file size, SHA-256, build time and signature comparison; personal paths are removed).
> - **To use it without installing Python, download `M24GA-…-win64.zip` from Releases, unzip it and run `M24GA.bat`.** Running from source needs Python 3.14 (see Usage below).
> - The app UI is Korean only for now. The documentation is available in English (this file and [docs/en/](docs/en/)); some generated reference pages (capabilities, fields, properties, actions) still have Korean descriptions, but their codes, names and types are language-neutral.

- A single script containing the core and the enabled mods is injected into the game with [Frida](https://frida.re).
- A mod can have a PC-side Python part, a window in the app, and an automatically generated settings screen.
- If the game build does not match, nothing is injected (the core stops the whole loader; mod-specific addresses only disable that mod).

## Usage

1. `pip install --target vendor -r requirements.txt` (creates `vendor/` in this folder)
2. Double-click `start_m24ga.bat` (or run `pythonw -X utf8 loader\app.py`)
3. Turn the loader on with the big button on the app's home screen; it connects automatically when the game starts.
4. For mods: open the app's **Open mods folder** (`Documents\M24GA\mods`), drop in a `.24mod` file and press **Refresh**.

From a terminal: `python -X utf8 loader/host.py` (`--list`, `--check`, `--now`, `--once`).

### CLI (every feature without the GUI)

`m24cli.bat <command>` or `python -X utf8 loader/cli.py <command>`. An AI agent can control everything directly without clicking through the GUI.

```
m24cli status                    loader state (game connection, build, mod summary)
m24cli mods                      list of mods and their state
m24cli mod <id>                  details of one mod
m24cli start [--now] [--wait 60] start the loader (--wait: wait until the game is connected)
m24cli stop                      stop the loader
m24cli run [--now] [--once]      run in the foreground (Ctrl+C to quit)
m24cli enable <id>               enable a mod
m24cli disable <id>              disable a mod
m24cli install <file.24mod>      install a mod
m24cli uninstall <id>            remove a mod
m24cli reload <id>               hot-reload a mod
m24cli grant <id>                grant a mod its risky capabilities
m24cli settings <id>             show settings
m24cli set <id> <key> <value>    change a setting
m24cli log <id>                  mod log
m24cli report <id>               report to hand to an AI
m24cli validate <path>           validate a mod
m24cli watch [--until hooked]    monitor state (JSON stream)
```

Add `--json` to any command for JSON output (for AI parsing). Help: `m24cli --help`.
While the app (or `m24cli run`) is running, CLI commands are forwarded to that loader (the game connection and mod logs live there). Details: [docs/en/CLI.md](docs/en/CLI.md).

### Building a distribution (developers)

`python -X utf8 tools/build_dist.py --embed python-3.14.x-embed-amd64.zip` → `dist/M24GA-<core version>-win64.zip`. It bundles the files tracked by git, `vendor/` and an embedded Python, and generates `M24GA.bat`, `m24cli.bat` and `THIRD_PARTY_LICENSES.txt`.

## Making mods

If you build with an AI (Claude Code, Cursor, ChatGPT, …), use the starter prompt in [docs/en/AI_GUIDE.md](docs/en/AI_GUIDE.md). The tools do the scaffolding and validation.

```
python -X utf8 tools/m24.py new my-mod --python --ui    # a working skeleton (includes AGENTS.md)
python -X utf8 tools/m24.py validate my-mod             # tells you where, why and how to fix
python -X utf8 tools/m24.py pack my-mod                 # validate and pack into .24mod
```

The reference is [docs/en/MODDING.md](docs/en/MODDING.md). Examples: [examples/hello](examples/hello) (settings, messages, mod window) and [examples/field-hook](examples/field-hook) (reading settings, reading game values, hooking functions). Game values you can read and write: [docs/FIELDS.md](docs/FIELDS.md) and [docs/PROPERTIES.md](docs/PROPERTIES.md); functions you can hook: [docs/FUNCTIONS.md](docs/FUNCTIONS.md); how to extend these lists: [docs/en/EXTENDING.md](docs/en/EXTENDING.md). If you change this repository with an AI, have it read [AGENTS.md](AGENTS.md). Tests: `python -X utf8 -m unittest discover -s tests`.

## Bundled mods

- `mods/ai-social-feed`: **DynamicAiFeed**. Replaces the social-feed fan comments with AI comments that read game data and the article text (API key required).
- `mods/dynamic-potential`: **DynamicPA** (dynamic potential). A player's potential ability (PA) rises or falls with their season's performance. It evaluates on the evaluation day (default 1 July) with preview, apply and undo. Ported from the FM24 Dynamic PA 0.9.5 model (GPL-3.0) ([mods/dynamic-potential/README.md](mods/dynamic-potential/README.md), credits in [NOTICE.md](mods/dynamic-potential/NOTICE.md)). It writes game values, so it needs the user's permission.
- `mods/player-value`: **EnhancedFee** (transfer-value adjustment). Values players of human-controlled clubs like AI clubs do, and applies a performance multiplier ([mods/player-value/README.md](mods/player-value/README.md)).
- `mods/dynamic-me`: **DynamicME** (match engine tuning). Applies engine packs without a restart (including tactical styles and xG) and lets you change engine values directly with 58 quick knobs and 950 detail values ([mods/dynamic-me/README.md](mods/dynamic-me/README.md)).
- Mods and loader by McR. The original model behind DynamicPA (and the performance calculation in EnhancedFee), **FM24 Dynamic PA**, was made by **도와줄께** ([original post v0.9.5](https://www.fmkorea.com/10506342571), [latest v1.0.6](https://www.fmkorea.com/10555327213)). It was ported with the author's permission.

## Warning

Mods run code in game memory and on this PC. Install only mods from sources you know. When the game is updated its addresses change and the loader may need an update (if they do not match, nothing is injected).

## License

GPL-3.0-or-later ([LICENSE](LICENSE)).
