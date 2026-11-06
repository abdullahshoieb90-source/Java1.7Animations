#!/usr/bin/env python3
"""
Static validator for the Java1.7Animations Bedrock resource pack.

Bedrock resource packs allow `//` and `/* */` comments inside JSON, and this
pack leans on that heavily (commented-out armour aliases, commented-out
particle blocks, ...), so every file is parsed with a string-aware comment
stripper before being handed to `json`.

    python3 tools/pack_check.py              # errors + warnings
    python3 tools/pack_check.py --verbose    # also show hints (vanilla ids etc.)
    python3 tools/pack_check.py --strict     # warnings fail the run too
    python3 tools/pack_check.py --json       # machine readable

Exit code: 0 = clean, 1 = errors (or warnings with --strict).

Layers
------
A pack file lives in the pack root or in a subpack folder
(`subpacks/<name>/...`). Subpacks override root files on purpose, so the same
identifier in the root *and* in a subpack is normal; a duplicate identifier
*inside one layer* is not, and is reported as an error. Animation alias names
are resolved inside the subpack first and fall back to the pack root, mirroring
how the game layers a subpack over the base pack.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Identifiers that vanilla Bedrock already defines.
VANILLA_IDENTIFIER_PREFIXES = (
    "animation.humanoid.",
    "animation.armor.",
    "animation.persona.",
    "animation.parrot.",
    "animation.skeleton.",
    "animation.shield.wield_first_person_blocking",
    "animation.player.attack.positions",
    "animation.player.crawl",
    "animation.player.look_at_target.",
    "animation.player.sleeping",
    "animation.player.swim.legs",
    "animation.player.first_person.",
    "animation.player.move.",
    "animation.player.riding.",
    "animation.player.bob",
    "animation.player.holding",
    "animation.player.sneaking",
    "animation.player.attack.",
    "animation.player.crossbow_",
    "animation.player.bow_equipped",
    "animation.player.melee_spear_",
    "controller.animation.player.melee_spear",
    "controller.animation.player.first_person_melee_spear",
    "animation.actor.",
    "geometry.humanoid.",
    "geometry.animated_",
    "geometry.default",
    "geometry.player.armor.",
    "geometry.bow_",
    "geometry.crossbow_",
    "geometry.shield",
    "geometry.trident",
    "geometry.spyglass",
    "geometry.cape",
    "geometry.item_sprite",
    "controller.render.item_default",
    "controller.render.item_sprite",
    "controller.render.bow",
    "controller.render.crossbow",
    "controller.render.shield",
    "controller.render.armor.",
    "controller.render.bow",
    "controller.render.crossbow",
    "controller.render.shield",
    "controller.animation.humanoid.",
    "controller.animation.persona.",
    "controller.animation.player.base",
    "controller.animation.player.hudplayer",
    "minecraft:",
)

# Materials vanilla Bedrock provides in its own entity.material.
VANILLA_MATERIALS = {
    "armor",
    "armor_enchanted",
    "armor_leather",
    "armor_leather_enchanted",
    "charged_creeper",
    "elytra",
    "elytra_glint",
    "entity",
    "entity_alphablend",
    "entity_alphatest",
    "entity_alphatest_change_color_glint",
    "entity_alphatest_glint",
    "entity_emissive",
    "entity_emissive_alpha",
    "entity_multitexture",
    "pattern",
    "pattern_glint",
    "player_animated",
    "player_spectator",
    "slime",
}

REQUIRED_DIRS = ("animations", "animation_controllers", "render_controllers", "entity")
REQUIRED_FILES = ("manifest.json",)
SKIP_DIRS = {"tools", "dist", "build", "node_modules", "__pycache__", ".git", ".vscode", "artifacts"}

DEFINITION_BLOCKS = (
    ("animations", "animation."),
    ("render_controllers", "controller.render."),
    ("animation_controllers", "controller.animation."),
)
ENTITY_SECTIONS = ("minecraft:client_entity", "minecraft:attachable")

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.hints = []
        self.info = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def hint(self, msg):
        self.hints.append(msg)

    def note(self, msg):
        self.info.append(msg)


def strip_comments(text: str) -> str:
    """Remove // and /* */ comments while respecting JSON string literals."""
    out = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_json(path: str):
    with open(path, encoding="utf-8-sig") as fh:
        return json.loads(strip_comments(fh.read()))


def layer_of(rel_path: str) -> str:
    parts = rel_path.replace(os.sep, "/").split("/")
    if len(parts) > 2 and parts[0] == "subpacks":
        return f"subpack:{parts[1]}"
    return "root"


def iter_pack_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            if name.endswith(".json"):
                yield os.path.relpath(os.path.join(dirpath, name), root)


def is_vanilla(identifier: str) -> bool:
    return identifier.startswith(VANILLA_IDENTIFIER_PREFIXES)


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def check_manifest(root: str, report: Report):
    path = os.path.join(root, "manifest.json")
    try:
        manifest = load_json(path)
    except FileNotFoundError:
        report.error("manifest.json: missing")
        return None
    except Exception as exc:  # noqa: BLE001
        report.error(f"manifest.json: invalid JSON -> {exc}")
        return None

    header = manifest.get("header") or {}
    modules = manifest.get("modules") or []
    if not modules:
        report.error("manifest.json: no modules declared")

    if not header.get("uuid"):
        report.error("manifest.json: header.uuid missing")
    seen = set()
    for uuid in [header.get("uuid")] + [m.get("uuid") for m in modules]:
        if not uuid:
            report.error("manifest.json: a module is missing its uuid")
            continue
        if not UUID_RE.match(uuid):
            report.error(f"manifest.json: not a valid UUID -> {uuid}")
        if uuid in seen:
            report.error(f"manifest.json: duplicate UUID -> {uuid}")
        seen.add(uuid)

    header_version = tuple(header.get("version") or ())
    if not header_version:
        report.error("manifest.json: header.version missing")
    for module in modules:
        if module.get("type") not in ("resources", "data", "skin_pack"):
            report.error(f"manifest.json: unknown module type -> {module.get('type')}")
        if tuple(module.get("version") or ()) != header_version:
            report.warn(
                f"manifest.json: module version {module.get('version')} != header version {header_version}"
            )

    subpacks_dir = os.path.join(root, "subpacks")
    declared = [sp.get("folder_name") for sp in manifest.get("subpacks") or []]
    if len(declared) != len(set(declared)):
        report.error("manifest.json: duplicate folder_name in the subpacks list")
    on_disk = (
        {d for d in os.listdir(subpacks_dir) if os.path.isdir(os.path.join(subpacks_dir, d))}
        if os.path.isdir(subpacks_dir)
        else set()
    )
    for name in sorted(n for n in declared if n):
        if name not in on_disk:
            report.error(f"manifest.json: subpack '{name}' is declared but subpacks/{name}/ is missing")
    for name in sorted(on_disk - {n for n in declared if n}):
        report.error(f"subpacks/{name}/: folder is not declared in manifest.json")

    for sp in manifest.get("subpacks") or []:
        folder = sp.get("folder_name")
        if not folder:
            report.error("manifest.json: subpack entry without folder_name")
            continue
        folder_path = os.path.join(subpacks_dir, folder)
        files = list(iter_pack_files(folder_path)) if os.path.isdir(folder_path) else []
        if not files:
            report.warn(f"subpacks/{folder}/: contains no JSON overrides")
        if (sp.get("name") or "").count("\u00a7") % 2:
            report.warn(f"subpacks/{folder}/: unbalanced colour codes in the display name")
        if sp.get("memory_tier") is None:
            report.warn(f"subpacks/{folder}/: no memory_tier declared")

    version = ".".join(str(p) for p in header_version)
    engine = ".".join(str(p) for p in header.get("min_engine_version") or ())
    report.note(f"manifest: v{version}, min engine v{engine}, {len(declared)} subpack(s)")
    return manifest


# --------------------------------------------------------------------------- #
# definitions
# --------------------------------------------------------------------------- #
def collect(root: str, report: Report):
    """Return (parsed, definitions). definitions: kind -> {identifier: [(layer, file)]}."""
    parsed = {}
    definitions = defaultdict(lambda: defaultdict(list))

    for rel in iter_pack_files(root):
        try:
            data = load_json(os.path.join(root, rel))
        except Exception as exc:  # noqa: BLE001
            report.error(f"{rel}: invalid JSON after comment stripping -> {exc}")
            continue
        if not isinstance(data, dict):
            report.error(f"{rel}: top level JSON is not an object")
            continue
        parsed[rel] = data
        layer = layer_of(rel)

        for block_name, prefix in DEFINITION_BLOCKS:
            block = data.get(block_name)
            if isinstance(block, dict):
                for identifier in block:
                    definitions[prefix][identifier].append((layer, rel))

        if "minecraft:geometry" in data:
            geometries = data["minecraft:geometry"]
            if not isinstance(geometries, list):
                report.error(f"{rel}: minecraft:geometry must be an array")
            else:
                for geometry in geometries:
                    identifier = (geometry.get("description") or {}).get("identifier")
                    if identifier:
                        definitions["geometry."][identifier].append((layer, rel))
                    else:
                        report.error(f"{rel}: minecraft:geometry entry without description.identifier")

        for section in ENTITY_SECTIONS:
            if section in data:
                identifier = (data[section].get("description") or {}).get("identifier")
                if identifier:
                    definitions[f"{section}:"][identifier].append((layer, rel))
                else:
                    report.error(f"{rel}: {section} without description.identifier")

        if "particle_effect" in data:
            identifier = (data["particle_effect"].get("description") or {}).get("identifier")
            if identifier:
                definitions["particle:"][identifier].append((layer, rel))
            else:
                report.error(f"{rel}: particle_effect without description.identifier")

    return parsed, definitions


def check_duplicate_layers(definitions, report: Report):
    for kind, table in definitions.items():
        for identifier, entries in table.items():
            per_layer = defaultdict(list)
            for layer, rel in entries:
                per_layer[layer].append(rel)
            for layer, files in per_layer.items():
                if len(files) > 1:
                    report.error(
                        f"{layer}: {kind}{identifier} defined more than once -> " + ", ".join(sorted(files))
                    )
    for section in ENTITY_SECTIONS:
        for identifier, entries in definitions.get(f"{section}:", {}).items():
            per_layer = defaultdict(list)
            for layer, rel in entries:
                per_layer[layer].append(rel)
            for layer, files in per_layer.items():
                if len(files) > 1:
                    report.error(
                        f"{layer}: {section} {identifier} declared more than once -> "
                        + ", ".join(sorted(files))
                    )


def collect_materials(root: str, report: Report):
    """Names defined by the pack's own materials/*.material files."""
    names = set()
    materials_dir = os.path.join(root, "materials")
    if not os.path.isdir(materials_dir):
        return names
    for name in sorted(os.listdir(materials_dir)):
        if not name.endswith(".material"):
            continue
        rel = os.path.join("materials", name)
        try:
            data = load_json(os.path.join(root, rel))
        except Exception as exc:  # noqa: BLE001
            report.error(f"{rel}: invalid JSON after comment stripping -> {exc}")
            continue
        block = data.get("materials")
        if isinstance(block, dict):
            names.update(k for k in block if k != "version")
    if names:
        report.note("materials: pack adds " + ", ".join(sorted(names)))
    return names


# --------------------------------------------------------------------------- #
# references
# --------------------------------------------------------------------------- #
def animation_aliases(parsed):
    """layer -> set of alias names declared in entity/attachable animations maps."""
    by_layer = defaultdict(set)
    for rel, data in parsed.items():
        for section in ENTITY_SECTIONS:
            if section in data:
                description = data[section].get("description") or {}
                by_layer[layer_of(rel)].update((description.get("animations") or {}).keys())
    return by_layer


def check_entity_maps(parsed, definitions, report: Report):
    defined = {kind: set(table) for kind, table in definitions.items()}
    for rel, data in parsed.items():
        for section in ENTITY_SECTIONS:
            if section not in data:
                continue
            description = data[section].get("description") or {}
            for alias, value in (description.get("animations") or {}).items():
                if not isinstance(value, str):
                    report.error(f"{rel}: animations['{alias}'] is not a string")
                    continue
                if value.startswith("controller.animation."):
                    if value not in defined["controller.animation."]:
                        _unresolved(report, rel, f"animations['{alias}'] -> {value}", value)
                elif value.startswith("animation."):
                    if value not in defined["animation."]:
                        _unresolved(report, rel, f"animations['{alias}'] -> {value}", value)
                else:
                    report.error(f"{rel}: animations['{alias}'] value '{value}' is not a valid identifier")
            for controller in description.get("render_controllers") or []:
                if isinstance(controller, str) and controller not in defined["controller.render."]:
                    _unresolved(report, rel, f"render controller {controller}", controller)
            geometries = description.get("geometry") or {}
            slots = geometries.items() if isinstance(geometries, dict) else []
            for slot, geometry in slots:
                if isinstance(geometry, str) and geometry not in defined["geometry."]:
                    _unresolved(report, rel, f"geometry['{slot}'] -> {geometry}", geometry)
            for slot, material in (description.get("materials") or {}).items():
                if isinstance(material, str):
                    if material not in VANILLA_MATERIALS and not material.startswith("ambient_uv"):
                        report.warn(f"{rel}: material '{material}' (slot {slot}) is not a vanilla material")
            for slot, texture in (description.get("textures") or {}).items():
                if not isinstance(texture, str):
                    report.error(f"{rel}: textures['{slot}'] is not a path string")


def _unresolved(report: Report, rel: str, what: str, identifier: str):
    if is_vanilla(identifier):
        report.hint(f"{rel}: {what} (vanilla, expected)")
    else:
        report.warn(f"{rel}: {what} is not defined in this pack")


def check_controller_aliases(parsed, report: Report):
    """
    Animation controllers address animations by the alias declared in an
    entity's `animations` map. The player entity file only exists inside
    subpacks, while the controllers sit in the pack root, so an alias counts as
    resolvable when *any* layer declares it.
    """
    aliases = animation_aliases(parsed)
    allowed = set().union(*aliases.values()) if aliases else set()

    missing = defaultdict(set)
    for rel, data in parsed.items():
        for controller_name, controller in (data.get("animation_controllers") or {}).items():
            if not isinstance(controller, dict):
                continue
            for state_name, state in (controller.get("states") or {}).items():
                if not isinstance(state, dict):
                    continue
                for entry in state.get("animations") or []:
                    names = [entry] if isinstance(entry, str) else list(entry)
                    for name in names:
                        if name.startswith(("animation.", "controller.")):
                            report.warn(
                                f"{rel}: {controller_name}/{state_name} animates the full identifier "
                                f"'{name}'; state animations reference alias names"
                            )
                        elif name not in allowed:
                            missing[name].add(f"{controller_name}/{state_name}")

    for name, where in sorted(missing.items()):
        sample = ", ".join(sorted(where)[:3])
        report.warn(f"alias '{name}' is animated by {len(where)} state(s) ({sample} ...) but no entity declares it")


def check_particles(parsed, definitions, report: Report):
    defined = set(definitions["particle:"])
    missing = defaultdict(set)
    for rel, data in parsed.items():
        for section in ENTITY_SECTIONS:
            if section in data:
                effects = (data[section].get("description") or {}).get("particle_effects") or {}
                for name, value in effects.items():
                    identifier = value.get("effect") if isinstance(value, dict) else value
                    if isinstance(identifier, str) and identifier not in defined:
                        missing[identifier].add(rel)
    for identifier, files in sorted(missing.items()):
        if is_vanilla(identifier):
            report.hint(f"particle {identifier} comes from vanilla ({len(files)} file(s))")
        else:
            report.warn(f"particle {identifier} is not defined in this pack ({len(files)} file(s))")


def check_subpack_overrides(root: str, report: Report):
    subpacks_dir = os.path.join(root, "subpacks")
    if not os.path.isdir(subpacks_dir):
        return
    redundant = 0
    for name in sorted(os.listdir(subpacks_dir)):
        base = os.path.join(subpacks_dir, name)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fname in sorted(filenames):
                if not fname.endswith(".json"):
                    continue
                sub_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(sub_path, base)
                root_path = os.path.join(root, rel)
                if os.path.isfile(root_path):
                    with open(sub_path, "rb") as a, open(root_path, "rb") as b:
                        if a.read() == b.read():
                            report.warn(f"subpacks/{name}/{rel}: byte-identical to {rel} (dead override)")
                            redundant += 1
    if not redundant:
        report.note("no redundant subpack overrides")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate the Java1.7Animations pack.")
    parser.add_argument("--root", default=ROOT, help="pack root to validate (default: repo root)")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--verbose", action="store_true", help="also print hints")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    report = Report()

    for name in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(root, name)):
            report.error(f"{name}: missing")
    for name in REQUIRED_DIRS:
        if not os.path.isdir(os.path.join(root, name)):
            report.error(f"{name}/: missing directory")

    check_manifest(root, report)
    parsed, definitions = collect(root, report)
    check_duplicate_layers(definitions, report)
    check_entity_maps(parsed, definitions, report)
    check_controller_aliases(parsed, report)
    check_particles(parsed, definitions, report)
    check_subpack_overrides(root, report)

    if not os.path.isdir(os.path.join(root, "textures")):
        report.note("no textures/: the pack relies on vanilla textures only")

    ok = not report.errors and not (args.strict and report.warnings)
    if args.json:
        payload = {
            "ok": ok,
            "errors": report.errors,
            "warnings": report.warnings,
            "hints": report.hints,
            "info": report.info,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Pack: {root}")
        for line in report.info:
            print(f"  info   {line}")
        if args.verbose:
            for line in report.hints:
                print(f"  hint   {line}")
        for line in report.warnings:
            print(f"  WARN   {line}")
        for line in report.errors:
            print(f"  ERROR  {line}")
        counts = f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
        if not args.verbose:
            counts += f", {len(report.hints)} hint(s) hidden (--verbose)"
        print(f"\n{'FAILED' if not ok else 'OK'} - {counts}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
