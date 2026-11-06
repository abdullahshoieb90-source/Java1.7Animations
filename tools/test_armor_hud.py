#!/usr/bin/env python3
"""Regression checks for the ported XeroxClient Armor HUD wiring."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pack_check  # noqa: E402


def load(rel):
    return json.loads(pack_check.strip_comments((ROOT / rel).read_text(encoding="utf-8")))


def controls(node):
    if isinstance(node, dict):
        for c in node.get("controls", []):
            yield from controls(c)
        for mod in node.get("modifications", []):
            for c in mod.get("value", []):
                yield from controls(c)
    elif isinstance(node, list):
        for c in node:
            yield from controls(c)


def named_controls(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict):
                yield k, v
                yield from named_controls(v)
            elif isinstance(v, list):
                for c in v:
                    yield from named_controls(c)
    elif isinstance(node, list):
        for c in node:
            yield from named_controls(c)


class ArmorHudTests(unittest.TestCase):
    def test_all_subpacks_update_effects_offscreen(self):
        for p in sorted((ROOT / "subpacks").glob("*/entity/player.entity.json")):
            d = json.loads(pack_check.strip_comments(p.read_text(encoding="utf-8")))
            scripts = d["minecraft:client_entity"]["description"]["scripts"]
            self.assertEqual(scripts.get("should_update_effects_offscreen"), "1.0", p)

    def test_all_subpacks_use_hud_gate_without_onscreen_culling(self):
        for p in sorted((ROOT / "subpacks").glob("*/entity/player.entity.json")):
            d = json.loads(pack_check.strip_comments(p.read_text(encoding="utf-8")))
            pre = d["minecraft:client_entity"]["description"]["scripts"]["pre_animation"]
            gate = [x for x in pre if "v.render_in_hud =" in x]
            self.assertEqual(len(gate), 1, p)
            self.assertIn("q.is_in_ui && q.is_alive", gate[0], p)
            self.assertNotIn("q.is_on_screen", gate[0], p)

    def test_all_subpacks_animate_armor_hud_unconditionally(self):
        for p in sorted((ROOT / "subpacks").glob("*/entity/player.entity.json")):
            d = json.loads(pack_check.strip_comments(p.read_text(encoding="utf-8")))
            animate = d["minecraft:client_entity"]["description"]["scripts"]["animate"]
            self.assertIn("armor_hud", animate, p)

    def test_icon_controllers_do_not_use_onscreen_part_visibility(self):
        d = load("render_controllers/armor_hud.render_controllers.json")
        for name, rc in d["render_controllers"].items():
            self.assertEqual(rc["part_visibility"], [{"*": True}], name)
            self.assertTrue(rc["geometry"].startswith("geometry.hud_"), name)
            self.assertTrue(rc["filter_lighting"], name)

    def test_hud_material_supports_overlay_and_color_mask(self):
        d = load("materials/entity.material")
        defines = d["materials"]["hud_armor:armor"]["+defines"]
        self.assertIn("USE_OVERLAY", defines)
        self.assertIn("USE_COLOR_MASK", defines)

    def test_ui_declares_hud_namespace(self):
        self.assertEqual(load("ui/hud_screen.json").get("namespace"), "hud")

    def test_root_panel_has_live_armor_hud_renderer(self):
        d = load("ui/hud_screen.json")
        found = [v for k, v in named_controls(d.get("root_panel", {})) if k == "armor_hud_renderer"]
        self.assertEqual(len(found), 1)
        r = found[0]
        self.assertEqual(r["renderer"], "live_player_renderer")
        self.assertFalse(r["allow_clipping"])
        self.assertEqual(r["size"], [16, 16])
        self.assertEqual(r["offset"], [18, 442])
        self.assertEqual(r["anchor_from"], "bottom_middle")
        self.assertEqual(r["anchor_to"], "bottom_middle")

    def test_armor_hud_does_not_depend_on_missing_xerox_toggle(self):
        text = (ROOT / "ui/hud_screen.json").read_text(encoding="utf-8")
        self.assertNotIn("mod_armorhud", text)
        self.assertNotIn("mod_paperdoll", text)


if __name__ == "__main__":
    unittest.main()
