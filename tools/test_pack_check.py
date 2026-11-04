#!/usr/bin/env python3
"""
Self-tests for tools/pack_check.py.

Run with:  python3 tools/test_pack_check.py

Each test builds a throw-away mini pack in a temp directory, breaks exactly one
thing, and asserts the validator reports it with the right severity. The
validator is imported, not shelled out, so failures point at the responsible
check.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pack_check  # noqa: E402

MANIFEST = {
    "format_version": 2,
    "header": {
        "name": "test",
        "description": "test",
        "uuid": "11111111-1111-4111-8111-111111111111",
        "version": [1, 0, 0],
        "min_engine_version": [1, 21, 0],
    },
    "modules": [
        {
            "type": "resources",
            "uuid": "22222222-2222-4222-8222-222222222222",
            "version": [1, 0, 0],
        }
    ],
    "subpacks": [{"folder_name": "default", "name": "Default", "memory_tier": 0}],
}

ANIMATION = {"format_version": "1.10.0", "animations": {"animation.test.idle": {"loop": True}}}
CONTROLLER = {
    "format_version": "1.10.0",
    "animation_controllers": {
        "controller.animation.test.root": {"initial_state": "default", "states": {"default": {"animations": ["idle"]}}}
    },
}
ENTITY = {
    "format_version": "1.10.0",
    "minecraft:client_entity": {
        "description": {
            "identifier": "minecraft:test",
            "materials": {"default": "entity_alphatest"},
            "textures": {"default": "textures/entity/test"},
            "geometry": {"default": "geometry.test"},
            "animations": {"idle": "animation.test.idle", "root": "controller.animation.test.root"},
            "render_controllers": ["controller.render.test"],
        }
    },
}
RENDER_CONTROLLER = {
    "format_version": "1.10.0",
    "render_controllers": {"controller.render.test": {"geometry": "Geometry.default", "materials": []}},
}
GEOMETRY = {
    "format_version": "1.12.0",
    "minecraft:geometry": [{"description": {"identifier": "geometry.test", "texture_width": 16, "texture_height": 16}, "bones": []}],
}


def write(root, rel, payload):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, indent=2)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def make_pack(root, **overrides):
    payloads = {
        "manifest.json": MANIFEST,
        "animations/test.animation.json": ANIMATION,
        "animation_controllers/test.animation_controllers.json": CONTROLLER,
        "render_controllers/test.render_controllers.json": RENDER_CONTROLLER,
        "models/entity/test.geo.json": GEOMETRY,
        "entity/placeholder.entity.json": {"format_version": "1.10.0", "minecraft:client_entity": {"description": {"identifier": "minecraft:placeholder", "materials": {"default": "entity_alphatest"}}}},
        "subpacks/default/entity/test.entity.json": ENTITY,
    }
    payloads.update(overrides)
    for rel, payload in payloads.items():
        if payload is None:
            continue
        write(root, rel, payload)


def run(root, strict=False, verbose=False):
    args = ["--root", root, "--json"]
    if strict:
        args.append("--strict")
    if verbose:
        args.append("--verbose")
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = pack_check.main(args)
    return code, json.loads(buf.getvalue())


class PackCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_pack_passes(self):
        make_pack(self.root)
        code, out = run(self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["warnings"], [])

    def test_comment_stripping_keeps_urls_and_strings(self):
        text = '{\n // a comment\n "a": "http://example.com//x", /* block */ "b": 1\n}'
        self.assertEqual(json.loads(pack_check.strip_comments(text)), {"a": "http://example.com//x", "b": 1})

    def test_invalid_json_is_an_error(self):
        make_pack(self.root, **{"animations/broken.animation.json": '{"animations": {,}}'})
        code, out = run(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("invalid JSON" in e for e in out["errors"]), out["errors"])

    def test_duplicate_identifier_in_same_layer_is_an_error(self):
        make_pack(self.root, **{"animations/dupe.animation.json": {"animations": {"animation.test.idle": {}}}})
        _, out = run(self.root)
        self.assertTrue(any("defined more than once" in e for e in out["errors"]), out["errors"])

    def test_subpack_may_override_root_file(self):
        make_pack(self.root, **{"subpacks/default/animations/test.animation.json": ANIMATION})
        code, out = run(self.root)
        self.assertEqual(code, 0, out)

    def test_manifest_uuid_validation(self):
        bad = json.loads(json.dumps(MANIFEST))
        bad["header"]["uuid"] = "not-a-uuid"
        make_pack(self.root, **{"manifest.json": bad})
        _, out = run(self.root)
        self.assertTrue(any("not a valid UUID" in e for e in out["errors"]), out["errors"])

    def test_manifest_duplicate_uuid(self):
        bad = json.loads(json.dumps(MANIFEST))
        bad["modules"][0]["uuid"] = bad["header"]["uuid"]
        make_pack(self.root, **{"manifest.json": bad})
        _, out = run(self.root)
        self.assertTrue(any("duplicate UUID" in e for e in out["errors"]), out["errors"])

    def test_undeclared_subpack_folder_is_an_error(self):
        make_pack(self.root, **{"subpacks/ghost/entity/test.entity.json": ENTITY})
        _, out = run(self.root)
        self.assertTrue(any("not declared in manifest.json" in e for e in out["errors"]), out["errors"])

    def test_missing_subpack_folder_is_an_error(self):
        bad = json.loads(json.dumps(MANIFEST))
        bad["subpacks"].append({"folder_name": "missing", "name": "Missing", "memory_tier": 0})
        make_pack(self.root, **{"manifest.json": bad})
        _, out = run(self.root)
        self.assertTrue(any("subpacks/missing/ is missing" in e for e in out["errors"]), out["errors"])

    def test_unresolved_animation_is_a_warning(self):
        entity = json.loads(json.dumps(ENTITY))
        entity["minecraft:client_entity"]["description"]["animations"]["ghost"] = "animation.test.ghost"
        make_pack(self.root, **{"subpacks/default/entity/test.entity.json": entity})
        code, out = run(self.root)
        self.assertEqual(code, 0, out)
        self.assertTrue(any("animation.test.ghost is not defined" in w for w in out["warnings"]), out["warnings"])

    def test_vanilla_identifier_is_only_a_hint(self):
        entity = json.loads(json.dumps(ENTITY))
        entity["minecraft:client_entity"]["description"]["animations"]["look"] = "animation.humanoid.look_at_target.default"
        make_pack(self.root, **{"subpacks/default/entity/test.entity.json": entity})
        _, out = run(self.root)
        self.assertEqual(out["warnings"], [])
        self.assertTrue(any("vanilla, expected" in h for h in out["hints"]), out["hints"])

    def test_unknown_material_warns(self):
        entity = json.loads(json.dumps(ENTITY))
        entity["minecraft:client_entity"]["description"]["materials"]["default"] = "not_a_material"
        make_pack(self.root, **{"subpacks/default/entity/test.entity.json": entity})
        _, out = run(self.root)
        self.assertTrue(any("not a vanilla material" in w for w in out["warnings"]), out["warnings"])

    def test_orphan_animation_alias_warns(self):
        controller = {
            "format_version": "1.10.0",
            "animation_controllers": {
                "controller.animation.test.root": {
                    "initial_state": "default",
                    "states": {"default": {"animations": ["nobody_declares_this"]}},
                }
            },
        }
        make_pack(self.root, **{"animation_controllers/test.animation_controllers.json": controller})
        _, out = run(self.root)
        self.assertTrue(any("nobody_declares_this" in w for w in out["warnings"]), out["warnings"])

    def test_redundant_subpack_override_warns(self):
        make_pack(self.root)
        root_anim = os.path.join(self.root, "animations/test.animation.json")
        sub_anim = os.path.join(self.root, "subpacks/default/animations/test.animation.json")
        os.makedirs(os.path.dirname(sub_anim), exist_ok=True)
        with open(root_anim, "rb") as src, open(sub_anim, "wb") as dst:
            dst.write(src.read())
        _, out = run(self.root)
        self.assertTrue(any("byte-identical" in w for w in out["warnings"]), out["warnings"])

    def test_particle_reference(self):
        entity = json.loads(json.dumps(ENTITY))
        entity["minecraft:client_entity"]["description"]["particle_effects"] = {"puff": "example:ghost"}
        make_pack(self.root, **{"subpacks/default/entity/test.entity.json": entity})
        _, out = run(self.root)
        self.assertTrue(any("example:ghost is not defined" in w for w in out["warnings"]), out["warnings"])

    def test_strict_promotes_warnings(self):
        entity = json.loads(json.dumps(ENTITY))
        entity["minecraft:client_entity"]["description"]["animations"]["ghost"] = "animation.test.ghost"
        make_pack(self.root, **{"subpacks/default/entity/test.entity.json": entity})
        code, out = run(self.root, strict=False)
        self.assertEqual(code, 0, out)
        code, out = run(self.root, strict=True)
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
