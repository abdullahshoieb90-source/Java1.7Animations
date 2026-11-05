#!/usr/bin/env python3
"""
Index a vanilla Bedrock *behaviour* pack dump (the `behavior_packs/` folder that
ships inside the game) into a compact JSON reference.

Modern Bedrock stores the vanilla behaviour data in `__brarchive` containers
instead of loose JSON, so `tools/brarchive.py` is used to read them.

    python3 tools/vanilla_index.py <behavior_packs-dir> --out docs/vanilla_index.json

The index records, per pack folder (which is what encodes the game version):

  * pack uuid / version / min_engine_version from manifest.json
  * every entity identifier shipped by that version
  * every entity component / component-group key used by that version

That answers questions the resource pack side cares about, e.g. "did 1.21.50
still ship `minecraft:player`" or "when did component X appear". The archive
counter (`json_entries` / `compiled_entries`) also flags entries that are stored
in the compiled binary form rather than as JSON.

Output is deterministic (sorted keys, no timestamps) so it diffs cleanly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brarchive  # noqa: E402
import pack_check  # noqa: E402

SKIP_PACKS = {"server_library", "server_ui_library"}


def read_manifest(pack_dir: str):
    path = os.path.join(pack_dir, "manifest.json")
    if not os.path.isfile(path):
        return {}
    try:
        manifest = pack_check.load_json(path)
    except Exception:  # noqa: BLE001 - vanilla manifests are plain JSON, be forgiving
        return {}
    header = manifest.get("header") or {}
    return {
        "name": header.get("name"),
        "uuid": header.get("uuid"),
        "version": header.get("version"),
        "min_engine_version": header.get("min_engine_version"),
    }


def index_entities(archive_path: str):
    """Return (identifiers, components, stats) for one entities.brarchive."""
    archive = brarchive.read_archive(archive_path)
    identifiers = []
    components = set()
    for doc in archive["documents"]:
        if not isinstance(doc, dict):
            continue
        entity = doc.get("minecraft:entity") or {}
        identifier = (entity.get("description") or {}).get("identifier")
        if identifier:
            identifiers.append(identifier)
        for key in (entity.get("components") or {}):
            components.add(key)
        for group in (entity.get("component_groups") or {}).values():
            for key in group or {}:
                components.add(key)
    return sorted(set(identifiers)), sorted(components), {
        "entries": archive["count"],
        "documents": len(archive["documents"]),
        "encoding": archive["encoding"],
    }


def build_index(root: str):
    packs = {}
    archives_seen = Counter()
    for folder in sorted(os.listdir(root)):
        pack_dir = os.path.join(root, folder)
        if not os.path.isdir(pack_dir) or folder in SKIP_PACKS:
            continue
        entry = {"manifest": read_manifest(pack_dir), "archives": {}}
        archive_dir = os.path.join(pack_dir, "__brarchive")
        if os.path.isdir(archive_dir):
            for name in sorted(os.listdir(archive_dir)):
                if not name.endswith(".brarchive"):
                    continue
                path = os.path.join(archive_dir, name)
                archives_seen[name] += 1
                try:
                    archive = brarchive.read_archive(path)
                except brarchive.BrarchiveError as exc:
                    entry["archives"][name] = {"error": str(exc)}
                    continue
                entry["archives"][name] = {
                    "entries": archive["count"],
                    "encoding": archive["encoding"],
                    "documents": len(archive["documents"]),
                }
                if name == "entities.brarchive":
                    ids, comps, stats = index_entities(path)
                    entry["entity_identifiers"] = ids
                    entry["component_keys"] = comps
                    entry["entity_stats"] = stats
        packs[folder] = entry

    return {
        "source": os.path.basename(os.path.abspath(root)),
        "pack_count": len(packs),
        "archive_kinds": dict(sorted(archives_seen.items())),
        "packs": packs,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Index a vanilla Bedrock behaviour pack dump.")
    parser.add_argument("root", help="path to the behavior_packs directory")
    parser.add_argument("--out", default="-", help="output JSON path, or - for stdout")
    parser.add_argument("--summary", action="store_true", help="print a short human summary")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.root):
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 1

    index = build_index(args.root)

    if args.out == "-":
        print(json.dumps(index, indent=2, sort_keys=True))
    else:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"wrote {args.out} ({os.path.getsize(args.out) / 1024:.1f} KiB, {index['pack_count']} packs)")

    if args.summary:
        print(f"\n{index['pack_count']} pack folders, archive kinds: {len(index['archive_kinds'])}")
        for folder, data in list(index["packs"].items()):
            ids = data.get("entity_identifiers")
            manifest = data.get("manifest") or {}
            version = ".".join(str(p) for p in manifest.get("version") or ()) or "?"
            entities = len(ids) if ids is not None else "-"
            print(f"  {folder:28} v{version:10} entities={entities}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
