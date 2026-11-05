"""Regression tests for the Armor HUD wiring (v2.6.1 + v2.6.2 fixes).

v2.6.1 addressed off-screen updates, q.is_on_screen gating, material defines,
and UI insertion. v2.6.2 addresses the remaining Android failure: the icon
quads are authored at y=500, but the player entity scale (0.9375) pulled them
down to y=468.75, outside the live_player_renderer viewport. A root-bone
animation must cancel that scale and stabilize the icons while moving.

These tests ensure the fixes stay in place across all 12 subpacks.
"""

import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS = ("helmet", "chestplate", "leggings", "boots")


def load(rel):
    return pack_check.load_json(os.path.join(ROOT, rel))


class ArmorHudEntityTests(unittest.TestCase):
    def setUp(self):
        self.entities = sorted(glob.glob(os.path.join(ROOT, "subpacks", "*", "entity", "player.entity.json")))
        self.assertEqual(len(self.entities), 12, "expected 12 subpack player entities")

    def test_offscreen_updates_enabled(self):
        for path in self.entities:
            data = pack_check.load_json(path)
            scripts = data["minecraft:client_entity"]["description"]["scripts"]
            self.assertEqual(
                scripts.get("should_update_effects_offscreen"), "1.0",
                f"{path}: should_update_effects_offscreen must be '1.0' so HUD scripts keep running",
            )

    def test_hud_gate_does_not_use_is_on_screen(self):
        for path in self.entities:
            data = pack_check.load_json(path)
            pre = data["minecraft:client_entity"]["description"]["scripts"]["pre_animation"]
            gate_lines = [s for s in pre if "v.j17_render_in_hud" in s and "=" in s and "q.is_in_ui" in s]
            self.assertTrue(gate_lines, f"{path}: missing HUD gate assignment")
            for line in gate_lines:
                self.assertNotIn("q.is_on_screen", line, f"{path}: HUD gate must not depend on q.is_on_screen")
                self.assertIn("q.is_in_ui", line)
                self.assertIn("q.is_alive", line)

    def test_hud_render_controllers_present(self):
        for path in self.entities:
            data = pack_check.load_json(path)
            rcs = data["minecraft:client_entity"]["description"]["render_controllers"]
            rc_names = set()
            for entry in rcs:
                if isinstance(entry, dict):
                    rc_names.update(entry.keys())
                elif isinstance(entry, str):
                    rc_names.add(entry)
            for slot in SLOTS:
                self.assertIn(f"controller.render.j17_armor_hud_{slot}", rc_names, f"{path}: missing {slot} HUD rc")

    def test_hud_geometry_and_material_slots(self):
        for path in self.entities:
            data = pack_check.load_json(path)
            desc = data["minecraft:client_entity"]["description"]
            self.assertEqual(desc["materials"].get("j17_armor_hud"), "j17_armor_hud", path)
            for slot in SLOTS:
                self.assertEqual(desc["geometry"].get(f"j17_hud_{slot}"), f"geometry.j17_armor_hud_{slot}", path)

    def test_hud_textures_present(self):
        for path in self.entities:
            data = pack_check.load_json(path)
            tex = data["minecraft:client_entity"]["description"]["textures"]
            hud_keys = [k for k in tex if k.startswith("j17_hud_")]
            self.assertEqual(len(hud_keys), 35, f"{path}: expected 35 HUD texture keys, got {len(hud_keys)}")


class ArmorHudRenderControllerTests(unittest.TestCase):
    def setUp(self):
        self.data = load("render_controllers/armor_hud.render_controllers.json")
        self.rcs = self.data["render_controllers"]

    def test_part_visibility_unconditional(self):
        for name, rc in self.rcs.items():
            pv = rc.get("part_visibility", [])
            for entry in pv:
                for bone, expr in entry.items():
                    self.assertIs(expr, True, f"{name}: part_visibility must be true (not q.is_on_screen)")

    def test_filter_lighting_enabled(self):
        for name, rc in self.rcs.items():
            self.assertIs(rc.get("filter_lighting"), True, f"{name}: filter_lighting must be true")
            self.assertIs(rc.get("ignore_lighting"), True, f"{name}: ignore_lighting must be true")

    def test_lowercase_resource_refs(self):
        for name, rc in self.rcs.items():
            self.assertTrue(rc["geometry"].startswith("geometry."), f"{name}: geometry ref must be lowercase")
            for mat_entry in rc["materials"]:
                for expr in mat_entry.values():
                    self.assertTrue(expr.startswith("material."), f"{name}: material ref must be lowercase")
            for tex_expr in rc["textures"]:
                self.assertTrue(tex_expr.startswith("array."), f"{name}: texture array ref must be lowercase")


class ArmorHudMaterialTests(unittest.TestCase):
    def test_use_overlay_and_color_mask(self):
        data = load("materials/entity.material")
        mat = data["materials"]["j17_armor_hud:armor"]
        defines = mat.get("+defines", [])
        self.assertIn("USE_OVERLAY", defines)
        self.assertIn("USE_COLOR_MASK", defines)


class ArmorHudUITests(unittest.TestCase):
    def test_hud_screen_namespace(self):
        data = load("ui/hud_screen.json")
        self.assertEqual(data.get("namespace"), "hud")

    def test_hud_screen_inserts_front(self):
        data = load("ui/hud_screen.json")
        mods = data["root_panel"]["modifications"]
        insert_mods = [m for m in mods if m.get("array_name") == "controls"]
        self.assertTrue(insert_mods)
        self.assertEqual(insert_mods[0]["operation"], "insert_front")
        values = insert_mods[0]["value"]
        self.assertTrue(any("j17_armor_hud@j17_armor_hud.armor_hud" in v for v in values))

    def test_armor_renderer_ignored(self):
        data = load("ui/hud_screen.json")
        self.assertIs(data["armor_renderer"]["ignored"], True)

    def test_renderer_layer_and_offset(self):
        data = load("ui/armor_hud.json")
        renderer = data["armor_hud"]["controls"][0]["armor_hud_renderer"]
        self.assertEqual(renderer["renderer"], "live_player_renderer")
        self.assertEqual(renderer["offset"], [-24, 485.5])
        self.assertGreaterEqual(renderer.get("layer", 0), 1)


class ArmorHudPlacementTests(unittest.TestCase):
    """v2.6.2: the y=500 quads must be scale-compensated into the renderer."""

    def test_root_bone_animation_cancels_player_scale(self):
        data = load("animations/player.armor_hud.animation.json")
        anim = data["animations"]["animation.player.j17_armor_hud"]
        self.assertIs(anim.get("loop"), True)
        bone = anim["bones"]["j17_armor_hud"]
        self.assertEqual(bone["scale"], "1.0 / 0.9375")
        self.assertIn("-20.0", bone["position"][1])
        self.assertIn("0.9375", bone["position"][1])
        self.assertIn("q.is_swimming", bone["position"][1])
        self.assertIn("q.is_crawling", bone["position"][1])
        self.assertIn("q.is_gliding", bone["rotation"][0])
        self.assertIn("q.is_riding", bone["rotation"][1])

    def test_animation_wired_in_all_subpacks(self):
        for path in sorted(glob.glob(os.path.join(ROOT, "subpacks", "*", "entity", "player.entity.json"))):
            desc = pack_check.load_json(path)["minecraft:client_entity"]["description"]
            self.assertEqual(
                desc["animations"].get("j17_armor_hud"),
                "animation.player.j17_armor_hud",
                f"{path}: missing HUD placement animation alias",
            )
            self.assertIn(
                {"j17_armor_hud": "q.is_in_ui"},
                desc["scripts"]["animate"],
                f"{path}: HUD placement animation must run while in the HUD",
            )

    def test_geometry_root_bone_matches_animation(self):
        data = load("models/entity/armor_hud.geo.json")
        for geo in data["minecraft:geometry"]:
            self.assertEqual(geo["bones"][0]["name"], "j17_armor_hud")
            cube = geo["bones"][1]["cubes"][0]
            self.assertEqual(cube["origin"][1], 500)
            self.assertEqual(cube["size"], [16, 16, 0])

    def test_light_color_multiplier(self):
        data = load("render_controllers/armor_hud.render_controllers.json")
        for name, rc in data["render_controllers"].items():
            self.assertEqual(rc.get("light_color_multiplier"), 1.25, name)


if __name__ == "__main__":
    unittest.main()
