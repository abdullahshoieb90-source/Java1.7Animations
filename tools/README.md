# Developer tools

Small, dependency-free Python 3 helpers for the pack. Nothing here is shipped
inside a `.mcpack`.

```bash
python3 tools/pack_check.py           # validate the pack
python3 tools/pack_check.py --verbose # also list vanilla ids that are referenced
python3 tools/test_pack_check.py      # self-tests for the validator
python3 tools/build_mcpack.py         # build artifacts/Java1.7Animations_v<version>.mcpack
python3 tools/build_mcpack.py --split # one merged archive per subpack

python3 tools/brarchive.py info path/to/entities.brarchive   # read vanilla __brarchive
python3 tools/vanilla_index.py /path/to/behavior_packs --out docs/vanilla_reference.json
python3 tools/test_brarchive.py       # self-tests for the archive reader
```

## `pack_check.py`

Bedrock parses resource pack JSON with comments, so the validator strips `//`
and `/* */` (string-aware, so `"http://..."` survives) before parsing. It then
checks:

| Check | Severity |
|---|---|
| JSON parses after comment stripping | error |
| `manifest.json` exists, has `header.uuid`, valid and unique UUIDs, known module type, module version == header version | error / warning |
| every `subpacks` entry exists on disk, and every folder on disk is declared | error |
| an identifier (`animation.*`, `controller.render.*`, `controller.animation.*`, geometry, entity) declared twice **in one layer** | error |
| references to identifiers that neither the pack nor vanilla defines | warning |
| `materials` values that are neither vanilla nor added by `materials/*.material` | warning |
| animation aliases animated by a controller but declared by no entity | warning |
| `particle_effects` pointing at particles the pack does not define | warning |
| a subpack file byte-identical to the root file it overrides | warning |
| vanilla identifiers in use | hint (`--verbose`) |

**Layers.** A pack file lives in the pack root or in `subpacks/<name>/...`.
Subpacks override root files on purpose, so `controller.render.player.first_person`
existing in both the root and `subpacks/red/` is expected. Duplicates inside a
single layer are real errors and are reported as such. Animation controllers
address animations through the alias names declared in an entity's `animations`
map; because the player entity only lives inside subpacks while the controllers
live in the root, an alias resolves if any layer declares it.

Exit code `0` means clean, `1` means errors (or warnings with `--strict`).
`--json` gives machine-readable output for CI.

## `build_mcpack.py`

A Bedrock resource pack is a zip with `manifest.json` at the root, so archives
are built directly:

* default: one archive with the `subpacks/` tree intact, so the in-game subpack
  selector still works;
* `--split`: one archive per subpack, with that subpack's files merged over the
  base pack and `subpacks` emptied in the manifest — handy when a platform or a
  test device picks the wrong subpack, or when you want a fixed configuration;
* validation runs first and aborts the build on failure (`--skip-check` to
  bypass, `--strict` to also fail on warnings).

Output is deterministic: entries are sorted and zip timestamps are pinned, so
rebuilding an unchanged pack produces byte-identical archives. Files land in
`artifacts/`, which is git-ignored.

## `brarchive.py`

From ~1.21 Bedrock ships the vanilla behaviour pack as `__brarchive` containers
instead of loose JSON. This reader opens them:

| encoding | meaning |
|---|---|
| `json` | one JSON document per header entry, separated by a few non-JSON bytes |
| `compiled` | binary chunked form (`item_catalog`, `items`, `shapes`); only names are exposed |
| `empty` | `count == 0`, e.g. the `server_*_library` packs |
| `unknown` | a codec that is not decoded yet (a few `scripts`/older `recipes`) |

The format is documented in the module docstring: 12-byte header (magic
`0xB125277D`, hash, count), then 256-byte name records, then the payload region.
The per-record `u32` is an opaque id, **not** a length — treating it as a length
is the mistake that makes naive parsers produce garbled documents.

## `vanilla_index.py`

Indexes a game-shipped `behavior_packs/` dump into `docs/vanilla_reference.json`:
per pack folder the manifest metadata, the entity identifiers, the component keys
and the encoding of every archive. See `docs/vanilla-notes.md` for what that
dump revealed (patch-layer folders, `minecraft:player` components, codec
coverage).
