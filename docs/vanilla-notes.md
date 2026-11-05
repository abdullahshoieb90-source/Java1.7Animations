# Notes on the vanilla Bedrock pack dump

These notes come from reading a `behavior_packs/` dump shipped with the game
(69 pack folders, `1.14` → `1.26.60`, 303 `__brarchive` containers). Everything
below is reproducible with `tools/brarchive.py` and `tools/vanilla_index.py`.

## 1. Vanilla data is no longer loose JSON

Every pack folder keeps loose `manifest.json` / `contents.json` (and
`loot_tables/`, `structures/`), but the actual entity, recipe, biome, trade and
item data lives in `<pack>/__brarchive/<kind>.brarchive`.

Consequences for this repo:

* you cannot diff the vanilla player entity against ours by looking for
  `entities/player.json` — it is inside `entities.brarchive`;
* the `contents.json` in each folder still lists the loose files, which is why
  the archive folder looks almost empty;
* `tools/brarchive.py` opens the containers, so the data *is* reachable.

## 2. The dump is incremental, not "one folder per version"

This is the important trap. The pack folders are **patch layers**:
`vanilla_1.21.50` contains only the entities that changed in that build. The
complete entity list lives in the base `vanilla` folder (96 entities in this
dump), and each versioned folder adds/overrides a few.

So `vanilla_1.26.60` reporting 11 entities does **not** mean 1.26.60 dropped the
other 85 — it means only 11 changed. Measure differences between two versions as
"base + patches up to that version", not folder by folder.

## 3. `minecraft:player` is a behaviour entity

`vanilla/__brarchive/entities.brarchive` contains `player.json` with
`identifier: "minecraft:player"`, and its components are gameplay-only:
`minecraft:breathable`, `minecraft:exhaustion_values`, `minecraft:insomnia`,
`minecraft:hurt_on_condition`, `minecraft:player.level`, … (22–24 components
depending on the pack layer).

Two things matter for the animations work:

* the entity exists server-side, which is why a client entity override is
  possible at all;
* newer layers add components the animations can query, e.g.
  `minecraft:apply_knockback_rules` appears by `vanilla_1.26.30` and is **not**
  present in `vanilla` or `vanilla_1.21.0` — a candidate for detecting knockback
  in animations on newer builds;
* `minecraft:hurt_on_condition` in 1.26.30 lists only `lava` at
  `damage_per_tick: 4`, i.e. the "hurt" damage types are no longer expressed
  there, so `q.has_damage`-style flags remain the only portable signal.

## 4. Encoding coverage of the reader

Across the 303 archives in the dump:

| encoding | archives | notes |
|---|---|---|
| `json` | 195 | payload is one JSON document per header entry, separated by a few non-JSON bytes |
| `empty` | 73 | `count == 0`, e.g. the `server_*_library` packs |
| `compiled` | 30 | binary chunked form: `item_catalog` (26), `items` (3), `shapes` (1) |
| `unknown` | 5 | 2 `scripts`, 2 older `recipes`, 1 older `items` — different codec, not decoded |

All 195 JSON archives return exactly as many documents as their header declares;
`tools/test_brarchive.py` pins that behaviour with synthetic fixtures.

## 5. Regenerating the index

```bash
python3 tools/vanilla_index.py /path/to/behavior_packs --out docs/vanilla_reference.json
```

`docs/vanilla_reference.json` (~416 KiB) records per pack folder: manifest
uuid/version/min_engine_version, every entity identifier, every component key,
and the encoding of each archive. It is committed so the pack's assumptions can
be checked without shipping the game dump itself (which is not redistributable).
