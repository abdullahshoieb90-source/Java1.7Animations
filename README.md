# Java1.7Animations

[![CI](https://github.com/abdullahshoieb90-source/Java1.7Animations/actions/workflows/ci.yml/badge.svg)](https://github.com/abdullahshoieb90-source/Java1.7Animations/actions/workflows/ci.yml)
[الشرح بالعربية](README.ar.md)

This resource pack attempts to faithfully port over many player animations from Minecraft Java Edition v1.7 to Minecraft Bedrock Edition. Contributions are welcome in the form of pull requests! Please submit a detailed issue if you have a bug report.

### Armor HUD (v2.6+):
The pack ships an always-on **Armor HUD** inspired by XeroxClient's: the vanilla armor-points bar is replaced by four item icons (helmet, chestplate, leggings, boots) above the hotbar, with empty-slot placeholders, leather dye tint, and turtle shell / elytra / copper / carved pumpkin support. It is an original implementation (no XeroxClient files are copied) and works entirely client-side through a `live_player_renderer` — no behavior pack required. The HUD position can be tweaked via `offset` in `ui/armor_hud.json` (default `[42, -40]`). Enchantment glint on the icons is not simulated.

### Working on the pack:
The repository is the pack itself: the root folder is what gets zipped into a `.mcpack`, and `subpacks/` holds the optional variants listed in `manifest.json`. Two dependency-free scripts live in [`tools/`](tools/README.md):

```bash
python3 tools/pack_check.py      # validate JSON, manifest, subpacks and cross-references
python3 tools/build_mcpack.py    # build artifacts/Java1.7Animations_v<version>.mcpack
```

Run the validator before opening a pull request — it catches the usual breakage (unbalanced comments, an id declared twice in the same layer, a subpack folder that is not declared in the manifest, a controller animating an alias no entity defines).

### CI & releases:
- **CI** (`.github/workflows/ci.yml`) runs the validator self-tests, validates the pack with `--strict`, builds the `.mcpack`, verifies the build is reproducible (byte-identical rebuild), and uploads the pack as a downloadable artifact on every push and pull request.
- **Releases** (`.github/workflows/release.yml`) publish a GitHub release with the `.mcpack`, SHA256 checksums and the matching CHANGELOG section when a version tag matching `manifest.json` is pushed:

```bash
git tag v2.6.1 && git push origin v2.6.1
```

The release job fails with a clear message if the tag does not match the manifest version (bump the manifest first).

### About Licensing:
This repository only exists for educational purposes, to aggregate bug reports, and solicit meaningful and quality contributions. If I could distribute an encrypted version of this pack on my own, I would, since theft is rampant in the MCBE mod and pack community. But that isn't possible without a lot of work. Hence, it doesn't seem harmful to "open source" this project. See [LICENSE](LICENSE) for exact terms of use.