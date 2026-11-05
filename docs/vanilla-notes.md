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

---

# Part 2 — the resource pack dump (`resource_packs/`)

Same container format, different payloads: 71 pack folders, 391 `__brarchive`
files, with `entity`, `animations`, `animation_controllers`,
`render_controllers`, `models`, `materials`, `particles`, `ui`, `textures`,
`font` and `sounds` archives. The reader needed no changes to handle them.

## 6. The vanilla base pack holds exactly one `minecraft:player` client entity

`vanilla part 1 …/__brarchive/entity.brarchive` has 147 entries. Exactly one of
them is the player client entity, and it declares:

* **52 animation aliases**, 10 `pre_animation` statements, `scripts.animate: ["root"]`
* geometry slots: only `default` and `cape`
* materials: `default`, `cape`, `animated`
* 3 render controllers: `controller.render.player.first_person`, `.third_person`, `.map`

The 16.60 layer repeats a tiny subset (`minecraft:cat`, `minecraft:sheep`), which
confirms the patch-layer model from Part 1 also applies here.

## 7. Versioned layers only patch the player entity

Only 13 of the 71 folders carry a player client entity:

| pack | aliases | geometry slots | pre_animation |
|---|---|---|---|
| 1.16.0 | 50 | cape, default | 10 |
| 1.17.0 | 50 | cape, default | 10 |
| 1.19.10 | 52 | cape, default | 10 |
| 1.20.10 | 56 | cape, default | 10 |
| 1.21.50 | 57 | cape, default | 10 |
| 1.21.90 | 58 | cape, default | 11 |
| **1.21.130** | **68** | cape, default | **64** |

Two consequences:

1. **A pack must declare every alias it still relies on itself.** Bedrock does
   not merge the entity file: `subpacks/*/entity/player.entity.json` fully
   replaces the vanilla description. Our pack is safe here — all 52 vanilla base
   aliases are still declared in every subpack — but the 1.21.130 additions are
   not, because they bind to animations we do not define.
2. **The armour overlay is still viable in 1.21.130.** Vanilla declares only
   `default` and `cape` geometry slots; every `player_armor_*` slot is ours, and
   `render_controllers` is still an overridable array. That is what the whole
   hurt-overlay feature is built on.

## 8. New first-class features as of 1.21.130

The 1.21.130 player entity grew from 58 to 68 aliases and from 11 to 64
`pre_animation` statements, and it changed spectator handling:

* render controllers are now spectator-aware:
  `controller.render.player.first_person_spectator` (ours matches this already)
  plus `|| query.is_spectator` guards;
* materials gained `spectator: player_spectator` (ours matches);
* new aliases bind to new vanilla animations — and this pack does not define
  them, so on 1.21.130+ the following vanilla features are effectively missing
  from our player:

| alias | binds to | ours defines it? |
|---|---|---|
| `crawling.no_right_arm` | `animation.player.crawl.no_right_arm` | no |
| `swimming.no_right_arm` | `animation.player.swim.no_right_arm` | no |
| `riding.root` | `animation.player.riding.root` | no |
| `holding_heavy_core` | `animation.player.holding_heavy_core` | no |
| `first_person_melee_spear_*` (4 aliases) | `animation.player.first_person.melee_spear_*` + `controller.animation.player.first_person_melee_spear` | no |
| `third_person_melee_spear_*` (4 aliases) | `animation.player.melee_spear_attack`, `animation.humanoid.melee_spear_*` | no |

The bodies are short and readable in the dump, which makes them cheap to port.
Two examples, verbatim:

```json
"animation.player.riding.root":    { "loop": true, "bones": { "root": { "position": [0.0, "variable.riding_y_offset ?? 0.0", 0.0] } } }
"animation.player.holding_heavy_core": { "loop": true, "bones": { "rightItem": { "scale": 0.7, "position": [-1.0, 0.0, -2.0] } } }
```

## 9. Regenerating the resource index

```bash
python3 tools/vanilla_index.py /path/to/resource_packs --resource \
    --out docs/vanilla_resource_index.json
```

`docs/vanilla_resource_index.json` (~105 KiB) keeps, per pack folder: manifest
metadata, archive encodings, and — for the 13 folders that ship one — the
`minecraft:player` client entity summary (animation aliases, geometry slots,
materials, render controllers, `scripts` keys, `animate` list, `pre_animation`
count).
