#!/usr/bin/env python3
"""Regression tests for Bedrock 1.21.130+ melee-spear compatibility."""

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
    "first_person_melee_spear_use": "animation.player.first_person.melee_spear_use",
    "first_person_melee_spear_hold": "animation.player.first_person.melee_spear_hold",
    "first_person_melee_spear_attack": "animation.player.first_person.melee_spear_attack",
    "first_person_melee_spear_controller": "controller.animation.player.first_person_melee_spear",
    "third_person_melee_spear_use": "animation.humanoid.melee_spear_use",
    "third_person_melee_spear_hold": "animation.humanoid.melee_spear_hold",
    "third_person_melee_spear_attack": "animation.player.melee_spear_attack",
    "third_person_melee_spear_controller": "controller.animation.player.melee_spear",
}

PUBLIC_VARIABLES = {
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
    def test_every_player_subpack_declares_the_spear_pipeline(self):
        self.assertEqual(len(PLAYER_PATHS), 12)
        for path in PLAYER_PATHS:
            with self.subTest(subpack=path.parts[-3]):
                data = load(path)["minecraft:client_entity"]["description"]
                scripts = data["scripts"]
                animations = data["animations"]
                for alias, target in SPEAR_ALIASES.items():
                    self.assertEqual(animations.get(alias), target)
                for variable in PUBLIC_VARIABLES:
                    self.assertEqual(scripts["variables"].get(variable), "public")
                self.assertEqual(scripts.get("should_update_effects_offscreen"), "1.0")
                self.assertIn(
                    "v.melee_spear_equipped = q.equipped_item_any_tag('slot.weapon.mainhand', 'minecraft:is_spear');",
                    scripts["pre_animation"],
                )

    def test_every_controller_layer_wires_both_perspectives(self):
        self.assertEqual(len(CONTROLLER_PATHS), 7)
        for path in CONTROLLER_PATHS:
            with self.subTest(layer=path.relative_to(ROOT).as_posix()):
                controllers = load(path)["animation_controllers"]
                for identifier in (
                    "controller.animation.player.melee_spear",
                    "controller.animation.player.first_person_melee_spear",
                ):
                    self.assertIn(identifier, controllers)
                    states = controllers[identifier]["states"]
                    self.assertEqual(set(states), {"hold", "use", "attack"})

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

    def test_first_person_spear_animations_control_the_item_and_java_arm_pose(self):
        animations = load(ROOT / "animations/player.first_person.animation.json")["animations"]
        for action in ("hold", "use", "attack"):
            with self.subTest(action=action):
                animation = animations[f"animation.player.first_person.melee_spear_{action}"]
                self.assertTrue(animation["loop"])
                self.assertIn("rightitem", animation["bones"])
                self.assertIn("rightarm", animation["bones"])
                self.assertEqual(len(animation["bones"]["rightitem"]["position"]), 3)
                self.assertEqual(len(animation["bones"]["rightitem"]["rotation"]), 3)

    def test_third_person_attack_also_supports_the_custom_armor_arm(self):
        animations = load(ROOT / "animations/player.animation.json")["animations"]
        bones = animations["animation.player.melee_spear_attack"]["bones"]
        self.assertIn("rightarm", bones)
        self.assertIn("rightarm_custom", bones)
        self.assertIn("rightitem", bones)


if __name__ == "__main__":
    unittest.main()
