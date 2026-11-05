#!/usr/bin/env python3
"""
Self-tests for tools/build_mcpack.py.

Run with:  python3 tools/test_build_mcpack.py

Each test builds a throw-away mini pack in a temp directory and asserts the
archive layout, exclusions, determinism and subpack merging behave as
documented. The builder is imported, not shelled out.
"""

import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_mcpack  # noqa: E402

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
            "description": "test",
            "type": "resources",
            "uuid": "22222222-2222-4222-8222-222222222222",
            "version": [1, 0, 0],
        }
    ],
    "subpacks": [
        {"folder_name": "default", "name": "Default", "memory_tier": 0},
        {"folder_name": "red", "name": "Red", "memory_tier": 0},
    ],
}


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def make_mini_pack(root):
    write(os.path.join(root, "manifest.json"), json.dumps(MANIFEST))
    write(
        os.path.join(root, "animations", "player.animation.json"),
        '// comment\n{"format_version": "1.8.0", "animations": {}}\n',
    )
    write(os.path.join(root, "entity", "player.entity.json"), '{"base": true}')
    write(os.path.join(root, "subpacks", "default", "entity", "player.entity.json"), '{"variant": "default"}')
    write(os.path.join(root, "subpacks", "red", "entity", "player.entity.json"), '{"variant": "red"}')
    write(os.path.join(root, "pack_icon.png"), "not really a png")
    write(os.path.join(root, "pack_icon_1024x1024.png"), "store art, must not ship")
    write(os.path.join(root, "README.md"), "docs")
    write(os.path.join(root, "tools", "helper.py"), "print('dev only')")
    write(os.path.join(root, ".git", "config"), "git internals")
    write(os.path.join(root, "artifacts", "old.mcpack"), "previous build")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "pack")
        os.makedirs(self.root)
        make_mini_pack(self.root)

    def build(self, *extra):
        out = os.path.join(self.tmp.name, "out.mcpack")
        code = build_mcpack.main(["--root", self.root, "--skip-check", "--out", out, *extra])
        self.assertEqual(code, 0)
        return out

    def names(self, archive):
        with zipfile.ZipFile(archive) as zf:
            return set(zf.namelist())

    def test_archive_layout_and_exclusions(self):
        names = self.names(self.build())
        self.assertIn("manifest.json", names)
        self.assertIn("animations/player.animation.json", names)
        self.assertIn("pack_icon.png", names)
        self.assertIn("subpacks/red/entity/player.entity.json", names)
        for bad in names:
            self.assertFalse(bad.startswith(("tools/", ".git/", "artifacts/", "subpacks/../")), bad)
        self.assertNotIn("pack_icon_1024x1024.png", names)
        self.assertNotIn("README.md", names)

    def test_build_is_deterministic(self):
        first = self.build()
        with open(first, "rb") as fh:
            data = fh.read()
        second = self.build()
        with open(second, "rb") as fh:
            self.assertEqual(fh.read(), data)

    def test_split_merge_overrides_base_and_empties_subpacks(self):
        entries = build_mcpack.collect_entries(self.root, merge_subpack="red", keep_subpacks=False)
        out = os.path.join(self.tmp.name, "merged.mcpack")
        build_mcpack.write_archive(out, entries, self.root, "red", None)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            self.assertFalse(any(n.startswith("subpacks/") for n in names))
            self.assertEqual(zf.read("entity/player.entity.json"), b'{"variant": "red"}')
            manifest = json.loads(zf.read("manifest.json"))
            self.assertEqual(manifest["subpacks"], [])
            self.assertIn("[red]", manifest["header"]["name"])

    def test_out_rejected_with_split(self):
        with self.assertRaises(SystemExit) as ctx:
            build_mcpack.main(
                ["--root", self.root, "--skip-check", "--split", "--out", os.path.join(self.tmp.name, "x.mcpack")]
            )
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
