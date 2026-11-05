# Java1.7Animations
This resource pack attempts to faithfully port over many player animations from Minecraft Java Edition v1.7 to Minecraft Bedrock Edition. Contributions are welcome in the form of pull requests! Please submit a detailed issue if you have a bug report.

### Working on the pack:
The repository is the pack itself: the root folder is what gets zipped into a `.mcpack`, and `subpacks/` holds the optional variants listed in `manifest.json`. Two dependency-free scripts live in [`tools/`](tools/README.md):

```bash
python3 tools/pack_check.py      # validate JSON, manifest, subpacks and cross-references
python3 tools/build_mcpack.py    # build artifacts/Java1.7Animations_v<version>.mcpack
```

Run the validator before opening a pull request — it catches the usual breakage (unbalanced comments, an id declared twice in the same layer, a subpack folder that is not declared in the manifest, a controller animating an alias no entity defines).

### About Licensing:
This repository only exists for educational purposes, to aggregate bug reports, and solicit meaningful and quality contributions. If I could distribute an encrypted version of this pack on my own, I would, since theft is rampant in the MCBE mod and pack community. But that isn't possible without a lot of work. Hence, it doesn't seem harmful to "open source" this project. See [LICENSE](LICENSE) for exact terms of use.