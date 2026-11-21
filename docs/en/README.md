# M24GA documentation (English)

The Korean originals sit one level up in [`docs/`](..). Each English page links to its Korean original and back.

| Page | What it is |
|---|---|
| [../../README.en.md](../../README.en.md) | Project overview, install, CLI quick list, bundled mods |
| [MODDING.md](MODDING.md) | The mod-making reference: `mod.json`, settings, the game-side `api`, Python `ctx`, mod window, safety, capabilities |
| [AI_GUIDE.md](AI_GUIDE.md) | A shorter guide for building mods **with an AI**, including a starter prompt and a "what exists / what does not" table |
| [CLI.md](CLI.md) | Every `m24cli` command |
| [EXTENDING.md](EXTENDING.md) | How to register new game slots and functions, and the semi-automatic discovery workflow |

## Generated reference pages (still Korean descriptions)

These pages are generated from the registries in `core/`. The **codes, names, types and ranges are language-neutral**; only the explanatory sentences are Korean.

| Page | Contents |
|---|---|
| [../CAPABILITIES.md](../CAPABILITIES.md) | Every capability a mod can declare, with its risk level |
| [../PROPERTIES.md](../PROPERTIES.md) | About 2,300 game property codes, with the writable ones in the "쓰기" (Writing) section: `safe` / `tested` / blocked |
| [../FIELDS.md](../FIELDS.md) | Registered memory slots and which of them are writable |
| [../FUNCTIONS.md](../FUNCTIONS.md) | Hookable game functions |
| [../ACTIONS.md](../ACTIONS.md) | The 198 game commands (actions) |
| [../NEWS.md](../NEWS.md) | News kinds and how `newsAdded`/`matchEnded` work |
| [../types/m24ga.d.ts](../types/m24ga.d.ts), [../types/m24ga.pyi](../types/m24ga.pyi) | Type definitions for the game-side JS and the Python `ctx` |

Tip for non-Korean readers: the type definition files and the `core/*.json` registries are the most precise references, and `python -X utf8 loader/cli.py prop-info <regex>` lists property codes from the command line.
