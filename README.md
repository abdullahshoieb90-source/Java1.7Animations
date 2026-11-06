# Java1.7Animations

[![CI](https://github.com/abdullahshoieb90-source/Java1.7Animations/actions/workflows/ci.yml/badge.svg)](https://github.com/abdullahshoieb90-source/Java1.7Animations/actions/workflows/ci.yml)
[الشرح بالعربية](README.ar.md)

This resource pack attempts to faithfully port over many player animations from Minecraft Java Edition v1.7 to Minecraft Bedrock Edition. Contributions are welcome in the form of pull requests! Please submit a detailed issue if you have a bug report.

**Bedrock 1.21.130+:** v2.5.4 replaces the earlier spear-compatibility approximation with a source-derived port of Java 1.21.11's spear animations in both perspectives. It includes per-tier use timing, Java's attack phases and easing curves, pivot-based item transforms, hit feedback, and all seven spear types in every subpack configuration.

The spear regression suite executes the packed Molang against an independent Java-math reference, including first-person `PoseStack` positions. These are static/source-derived checks, not a substitute for an in-game visual comparison. Bedrock `rightitem` conversion was cross-checked against the [Fixed Vanilla integration in MADLAD3718/The-Crew-SMP](https://github.com/MADLAD3718/The-Crew-SMP).

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
git tag v2.5.4 && git push origin v2.5.4
```

The release job fails with a clear message if the tag does not match the manifest version (bump the manifest first).

### About Licensing:
This repository only exists for educational purposes, to aggregate bug reports, and solicit meaningful and quality contributions. If I could distribute an encrypted version of this pack on my own, I would, since theft is rampant in the MCBE mod and pack community. But that isn't possible without a lot of work. Hence, it doesn't seem harmful to "open source" this project. See [LICENSE](LICENSE) for exact terms of use.