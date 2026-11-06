#!/usr/bin/env python3
"""Structural regression tests for the Java spear pipeline on Bedrock 1.21.130+."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pack_check  # noqa: E402


PLAYER_PATHS = sorted((ROOT / "subpacks").glob("*/entity/player.entity.json"))
CONTROLLER_PATHS = [ROOT / "animation_controllers/player.animation_controllers.json"] + sorted(
    (ROOT / "subpacks").glob("*/animation_controllers/player.animation_controllers.json")
)

SPEAR_ALIASES = {
    "first_person_melee_spear_base": "animation.player.first_person.melee_spear_base",
    "first_person_melee_spear_use": "animation.player.first_person.melee_spear_use",
    "first_person_melee_spear_hold": "animation.player.first_person.melee_spear_hold",
    "first_person_melee_spear_attack": "animation.player.first_person.melee_spear_attack",
    "first_person_melee_spear_controller": "controller.animation.player.first_person_melee_spear",
    "third_person_melee_spear_use": "animation.humanoid.melee_spear_use",
    "third_person_melee_spear_hold": "animation.humanoid.melee_spear_hold",
    "third_person_melee_spear_attack": "animation.player.melee_spear_attack",
    "third_person_melee_spear_controller": "controller.animation.player.melee_spear",
}

REMOVED_ATTACHABLE_VARIABLES = {
    "variable.fp_melee_spear_use_attachable_rotation_z",
    "variable.tp_melee_spear_use_attachable_rotation_z",
    "variable.fp_melee_spear_attack_attachable_rotation_z",
    "variable.tp_melee_spear_attack_attachable_position_z",
}


def load(path):
    return pack_check.load_json(str(path))


def referenced_animations(entries):
    names = set()
    for entry in entries:
        if isinstance(entry, str):
            names.add(entry)
        elif isinstance(entry, dict):
            names.update(entry)
    return names


class SpearCompatibilityTests(unittest.TestCase):
    def test_every_player_subpack_declares_the_complete_pipeline(self):
        self.assertEqual(len(PLAYER_PATHS), 12)
        for path in PLAYER_PATHS:
            with self.subTest(subpack=path.parts[-3]):
                data = load(path)["minecraft:client_entity"]["description"]
                scripts = data["scripts"]
                animations = data["animations"]
                for alias, target in SPEAR_ALIASES.items():
                    self.assertEqual(animations.get(alias), target)
                self.assertEqual(scripts["variables"].get("variable.melee_spear_equipped"), "public")
                for variable in REMOVED_ATTACHABLE_VARIABLES:
                    self.assertNotIn(variable, scripts["variables"])
                self.assertEqual(scripts.get("should_update_effects_offscreen"), "1.0")
                joined = "\n".join(scripts["pre_animation"])
                self.assertIn("q.equipped_item_any_tag('slot.weapon.mainhand', 'minecraft:is_spear')", joined)
                self.assertIn("q.ticks_since_last_kinetic_weapon_hit", joined)
                self.assertNotIn("q.base_swing_duration", joined)

    def test_every_controller_layer_wires_both_perspectives_and_overlap(self):
        self.assertEqual(len(CONTROLLER_PATHS), 7)
        for path in CONTROLLER_PATHS:
            with self.subTest(layer=path.relative_to(ROOT).as_posix()):
                controllers = load(path)["animation_controllers"]
                third = controllers["controller.animation.player.melee_spear"]["states"]
                first = controllers["controller.animation.player.first_person_melee_spear"]["states"]
                self.assertEqual(set(third), {"hold", "use", "attack"})
                self.assertEqual(set(first), {"hold", "use", "attack"})

                self.assertEqual(
                    referenced_animations(third["use"]["animations"]),
                    {
                        "third_person_melee_spear_hold",
                        "third_person_melee_spear_attack",
                        "third_person_melee_spear_use",
                    },
                )
                self.assertEqual(
                    third["use"]["animations"][1],
                    {"third_person_melee_spear_attack": "v.attack_time > 0.0"},
                )
                self.assertEqual(
                    third["use"]["animations"][2], "third_person_melee_spear_use"
                )
                for action in ("hold", "use", "attack"):
                    entries = first[action]["animations"]
                    self.assertEqual(entries[0], "first_person_melee_spear_base")
                    self.assertEqual(entries[1], f"first_person_melee_spear_{action}")
                    self.assertNotIn("blend_transition", first[action])

                root_states = controllers["controller.animation.player.root"]["states"]
                first_person = root_states["first_person"]["animations"]
                third_person = root_states["third_person"]["animations"]
                self.assertIn("first_person_melee_spear_controller", referenced_animations(first_person))
                self.assertIn("third_person_melee_spear_controller", referenced_animations(third_person))
                generic_attacks = [
                    condition
                    for entry in first_person + third_person
                    if isinstance(entry, dict)
                    for name, condition in entry.items()
                    if name in {"first_person_attack_controller", "attack.rotations"}
                ]
                self.assertEqual(len(generic_attacks), 2)
                for condition in generic_attacks:
                    self.assertIn("!v.melee_spear_equipped", condition)

    def test_first_person_base_and_dynamic_transforms_are_present(self):
        animations = load(ROOT / "animations/player.first_person.animation.json")["animations"]
        base = animations["animation.player.first_person.melee_spear_base"]
        self.assertTrue(base["override_previous_animation"])
        self.assertEqual(set(base["bones"]), {"rightarm", "rightitem"})
        for action in ("hold", "use", "attack"):
            with self.subTest(action=action):
                animation = animations[f"animation.player.first_person.melee_spear_{action}"]
                self.assertTrue(animation["loop"])
                self.assertFalse(animation["override_previous_animation"])
                self.assertIn("rightitem", animation["bones"])
                self.assertEqual(len(animation["bones"]["rightitem"]["position"]), 3)
        use_rotation = animations["animation.player.first_person.melee_spear_use"]["bones"]["rightitem"]["rotation"]
        self.assertEqual([list(axis) for axis in use_rotation], [["x"], ["y"]])

    def test_third_person_hold_use_and_attack_cover_custom_armor_arms(self):
        humanoid = load(ROOT / "animations/humanoid.animation.json")["animations"]
        for action in ("hold", "use"):
            bones = humanoid[f"animation.humanoid.melee_spear_{action}"]["bones"]
            self.assertIn("rightarm", bones)
            self.assertIn("rightarm_custom", bones)
        attack = load(ROOT / "animations/player.animation.json")["animations"]["animation.player.melee_spear_attack"]
        self.assertIn("rightarm", attack["bones"])
        self.assertIn("rightarm_custom", attack["bones"])
        self.assertIn("rightitem", attack["bones"])

    def test_spear_attachable_uses_java_display_and_no_duplicate_recoil(self):
        animations = load(ROOT / "animations/attachables/spear.animation.json")["animations"]
        self.assertIn("animation.spear.held_first_person", animations)
        self.assertIn("animation.spear.held_third_person", animations)
        hit = animations["animation.spear.hit"]
        self.assertNotIn("bones", hit)
        self.assertEqual(hit["sound_effects"]["0.0"]["effect"], "hit")
        geometry = load(ROOT / "models/entity/spear.geo.json")["minecraft:geometry"][0]
        self.assertEqual(geometry["description"]["identifier"], "geometry.spear")
        self.assertEqual(geometry["bones"][0]["pivot"], [0.0, 24.0, 0.0])


if __name__ == "__main__":
    unittest.main()
