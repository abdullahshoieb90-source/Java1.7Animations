#!/usr/bin/env python3
"""Numerically compare the packed Molang with Java 1.21.11 spear math."""

from __future__ import annotations

import math
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pack_check  # noqa: E402
import spear_java_reference as java  # noqa: E402


PLAYER_PATHS = sorted((ROOT / "subpacks").glob("*/entity/player.entity.json"))
WOODEN = {"delay": 15.0, "dismount": 100.0, "knockback": 200.0, "damage": 300.0}
NETHERITE = {"delay": 8.0, "dismount": 50.0, "knockback": 110.0, "damage": 175.0}


class MolangMath:
    """The degree-based/trilinear Molang functions used by the spear block."""

    @staticmethod
    def clamp(value, low, high):
        return max(low, min(high, value))

    @staticmethod
    def inverse_lerp(start, end, value):
        return (value - start) / (end - start)

    @staticmethod
    def sin(degrees):
        return math.sin(math.radians(degrees))

    @staticmethod
    def cos(degrees):
        return math.cos(math.radians(degrees))

    def __getattr__(self, name):
        if name.startswith("ease_"):
            easing = getattr(java, name.removeprefix("ease_"))

            def lerped(start, end, value):
                return start + (end - start) * easing(value)

            return lerped
        raise AttributeError(name)


MOLANG = MolangMath()
NAME = re.compile(r"\b([vtq])\.([A-Za-z0-9_]+)")
INITIALIZER = re.compile(r"v\.([a-z0-9_]+) = (-?[0-9.]+);")


def python_expression(expression):
    if isinstance(expression, (int, float)):
        return repr(expression)
    expression = expression.replace("math.", "m.")
    return NAME.sub(lambda match: f"{match.group(1)}_{match.group(2)}", expression)


def evaluate_expression(expression, environment):
    return eval(python_expression(expression), {"__builtins__": {}, "m": MOLANG}, environment)


def evaluate_player(path, *, use_ticks=0.0, attack_time=0.0, hit_ticks=20.0, frame_alpha=0.0,
                    swim_amount=0.0, gliding=0.0, tier=WOODEN):
    """Execute only the self-contained spear pre_animation block."""
    description = pack_check.load_json(str(path))["minecraft:client_entity"]["description"]
    scripts = description["scripts"]
    environment = {
        "m": MOLANG,
        "v_item_use_duration": float(use_ticks),
        "v_attack_time": float(attack_time),
        "v_swim_amount": float(swim_amount),
        "v_melee_spear_equipped": 1.0,
        "q_is_gliding": float(gliding),
        "q_ticks_since_last_kinetic_weapon_hit": float(hit_ticks),
        "q_frame_alpha": float(frame_alpha),
        "q_kinetic_weapon_delay": tier["delay"],
        "q_kinetic_weapon_dismount_duration": tier["dismount"],
        "q_kinetic_weapon_knockback_duration": tier["knockback"],
        "q_kinetic_weapon_damage_duration": tier["damage"],
    }
    for statement in scripts["initialize"]:
        match = INITIALIZER.fullmatch(statement.strip())
        if match and match.group(1) in {
            "kinetic_weapon_forward_movement",
            "melee_spear_attack_raise_end",
            "melee_spear_attack_thrust_end",
            "melee_spear_attack_recover_start",
        }:
            environment[f"v_{match.group(1)}"] = float(match.group(2))

    started = False
    for statement in scripts["pre_animation"]:
        code = statement.strip()
        if code.startswith("v.item_use_duration ="):
            started = True
            continue  # use_ticks is the already interpolated Java input.
        if not started:
            continue
        if code.startswith("v.melee_spear_equipped =") or code.startswith("(v.melee_spear_equipped)") or code == "};":
            continue
        target, expression = code.rstrip(";").split("=", 1)
        target = python_expression(target.strip())
        value = evaluate_expression(expression.strip(), environment)
        environment[target] = value
    return environment


def assert_vector(test, actual, expected, places=7):
    test.assertEqual(len(actual), len(expected))
    for index, (a, e) in enumerate(zip(actual, expected)):
        test.assertAlmostEqual(a, e, places=places, msg=f"component {index}: {actual} != {expected}")


class SpearJavaPortTests(unittest.TestCase):
    def test_all_subpacks_have_identical_java_math(self):
        def spear_statements(path):
            scripts = pack_check.load_json(str(path))["minecraft:client_entity"]["description"]["scripts"]
            start = next(i for i, value in enumerate(scripts["pre_animation"]) if value.startswith("v.item_use_duration ="))
            return scripts["pre_animation"][start:]

        expected = spear_statements(PLAYER_PATHS[0])
        self.assertEqual(len(PLAYER_PATHS), 12)
        for path in PLAYER_PATHS[1:]:
            with self.subTest(subpack=path.parts[-3]):
                self.assertEqual(spear_statements(path), expected)

    def test_java_constants_are_not_bedrock_duration_approximations(self):
        env = evaluate_player(PLAYER_PATHS[0])
        self.assertEqual(env["v_kinetic_weapon_forward_movement"], 0.38)
        self.assertEqual(env["v_melee_spear_attack_raise_end"], 0.05)
        self.assertEqual(env["v_melee_spear_attack_thrust_end"], 0.2)
        self.assertEqual(env["v_melee_spear_attack_recover_start"], 0.4)
        attack = java.attack_params(0.125)
        self.assertAlmostEqual(attack["raise"], 1.0)
        self.assertAlmostEqual(attack["thrust"], 0.25)
        self.assertAlmostEqual(attack["fp_thrust"], 1.0876975)
        self.assertAlmostEqual(java.attack_params(0.7)["recover"], 0.5)

    def test_use_params_match_java_for_multiple_tiers_and_ticks(self):
        variable_names = {
            "raise": "v_melee_spear_use_raise_progress",
            "start": "v_melee_spear_use_raise_progress_start",
            "middle": "v_melee_spear_use_raise_progress_middle",
            "end": "v_melee_spear_use_raise_progress_end",
            "sway": "v_melee_spear_use_sway_progress",
            "lower": "v_melee_spear_use_lower_progress",
            "back": "v_melee_spear_use_raise_back_progress",
            "intensity": "v_melee_spear_use_sway_intensity",
            "slow": "v_melee_spear_use_sway_scale_slow",
            "fast": "v_melee_spear_use_sway_scale_fast",
        }
        for tier in (WOODEN, NETHERITE):
            for ticks in (0.0, 3.5, 7.5, 15.0, 45.0, 95.0, 130.0, 175.0, 205.0, 315.0):
                with self.subTest(tier=tier["delay"], ticks=ticks):
                    env = evaluate_player(PLAYER_PATHS[0], use_ticks=ticks, tier=tier)
                    expected = java.use_params(ticks, **tier)
                    for key, variable in variable_names.items():
                        self.assertAlmostEqual(env[variable], expected[key], places=7, msg=key)

    def test_attack_curves_match_java(self):
        for attack_time in (0.0, 0.025, 0.05, 0.125, 0.2, 0.4, 0.7, 1.0):
            with self.subTest(attack_time=attack_time):
                env = evaluate_player(PLAYER_PATHS[0], attack_time=attack_time)
                expected = java.attack_params(attack_time)
                self.assertAlmostEqual(env["v_melee_spear_attack_raise_scale"], expected["raise"])
                self.assertAlmostEqual(env["v_melee_spear_attack_thrust_scale"], expected["thrust"])
                self.assertAlmostEqual(env["v_fp_melee_spear_attack_thrust_scale"], expected["fp_thrust"])
                self.assertAlmostEqual(env["v_melee_spear_attack_recover_scale"], expected["recover"])
                self.assertAlmostEqual(
                    env["v_tp_melee_spear_attack_arm_rotation_x"],
                    90.0 * expected["raise"] - 120.0 * expected["thrust"] + 30.0 * expected["recover"],
                )

    def test_hit_feedback_uses_java_in_out_sine_recovery(self):
        for ticks in (0.0, 1.0, 2.0, 3.0, 6.5, 10.0, 20.0):
            with self.subTest(ticks=ticks):
                env = evaluate_player(PLAYER_PATHS[0], hit_ticks=ticks)
                self.assertAlmostEqual(
                    env["v_melee_spear_use_hit_feedback_amount"], java.hit_feedback(ticks)
                )
        self.assertAlmostEqual(java.hit_feedback(2.0), 0.375)
        self.assertAlmostEqual(java.hit_feedback(6.5), 0.2)

    def test_first_person_use_matches_the_java_pose_stack(self):
        animations = pack_check.load_json(str(ROOT / "animations/player.first_person.animation.json"))["animations"]
        bone = animations["animation.player.first_person.melee_spear_use"]["bones"]["rightitem"]
        for ticks, hit in ((0.0, 20.0), (7.5, 20.0), (45.0, 2.0), (130.0, 6.5), (205.0, 20.0), (315.0, 20.0)):
            with self.subTest(ticks=ticks, hit=hit):
                env = evaluate_player(PLAYER_PATHS[0], use_ticks=ticks, hit_ticks=hit)
                params = java.use_params(ticks, **WOODEN)
                expected = java.first_person_use(params, java.hit_feedback(hit))
                actual = [evaluate_expression(value, env) for value in bone["position"]]
                assert_vector(self, actual, expected["position"])
                self.assertAlmostEqual(env["v_fp_melee_spear_use_item_rotation_x"], expected["rotation_x"])
                self.assertAlmostEqual(env["v_fp_melee_spear_use_item_rotation_y"], expected["rotation_y"])

    def test_first_person_attack_matches_the_java_pose_stack(self):
        animations = pack_check.load_json(str(ROOT / "animations/player.first_person.animation.json"))["animations"]
        bone = animations["animation.player.first_person.melee_spear_attack"]["bones"]["rightitem"]
        for attack_time in (0.0, 0.025, 0.125, 0.2, 0.4, 0.7, 1.0):
            with self.subTest(attack_time=attack_time):
                env = evaluate_player(PLAYER_PATHS[0], attack_time=attack_time)
                expected = java.first_person_attack(java.attack_params(attack_time))
                actual = [evaluate_expression(value, env) for value in bone["position"]]
                assert_vector(self, actual, expected["position"])
                self.assertAlmostEqual(env["v_fp_melee_spear_attack_item_rotation_x"], expected["rotation_x"])

    def test_third_person_source_angles_translations_and_arm_pose(self):
        for ticks, attack_time, hit in ((0.0, 0.0, 20.0), (45.0, 0.125, 2.0), (130.0, 0.7, 6.5), (205.0, 0.0, 20.0)):
            with self.subTest(ticks=ticks, attack_time=attack_time):
                env = evaluate_player(
                    PLAYER_PATHS[0], use_ticks=ticks, attack_time=attack_time, hit_ticks=hit
                )
                params = java.use_params(ticks, **WOODEN)
                attack = java.attack_params(attack_time)
                expected_arm = java.third_person_use_arm(params)
                self.assertAlmostEqual(env["v_tp_melee_spear_use_arm_rotation_x"], expected_arm["x"])
                self.assertAlmostEqual(env["v_tp_melee_spear_use_arm_rotation_y"], expected_arm["y"])
                self.assertAlmostEqual(env["v_tp_melee_spear_use_arm_rotation_z"], expected_arm["z"])
                expected_item = java.third_person_item(params, attack, java.hit_feedback(hit))
                self.assertAlmostEqual(env["v_tp_melee_spear_use_item_position_y"], expected_item["translation_y"])
                self.assertAlmostEqual(env["v_tp_melee_spear_use_item_rotation_x"], expected_item["rotation_x"])
                self.assertAlmostEqual(env["v_tp_melee_spear_use_item_rotation_z"], expected_item["rotation_z"])
                expected_attack = java.third_person_attack_item(attack)
                self.assertAlmostEqual(env["v_tp_melee_spear_attack_item_rotation_x"], expected_attack["rotation_x"])
                self.assertAlmostEqual(env["v_tp_melee_spear_attack_forward_movement"], expected_attack["forward"])

    def test_third_person_hold_uses_java_pitch_swim_and_clamps(self):
        for swim, gliding in ((0.0, 0.0), (0.5, 0.0), (1.0, 0.0), (0.0, 1.0)):
            with self.subTest(swim=swim, gliding=gliding):
                env = evaluate_player(PLAYER_PATHS[0], swim_amount=swim, gliding=gliding)
                self.assertAlmostEqual(
                    env["v_tp_melee_spear_base_arm_rotation_x"],
                    java.third_person_hand_base(0.0, swim + gliding),
                )
        humanoid = pack_check.load_json(str(ROOT / "animations/humanoid.animation.json"))["animations"]
        rotation = humanoid["animation.humanoid.melee_spear_hold"]["bones"]["rightarm"]["rotation"]
        self.assertIn("-120.0, 30.0", rotation[0])
        self.assertIn("-60.0, 60.0", rotation[1])
        self.assertIn("- 5.729578", rotation[1])
        self.assertNotIn("is_sneaking", " ".join(map(str, rotation)))

    def test_dynamic_item_transforms_are_zero_at_neutral_endpoints(self):
        fp = pack_check.load_json(str(ROOT / "animations/player.first_person.animation.json"))["animations"]
        humanoid = pack_check.load_json(str(ROOT / "animations/humanoid.animation.json"))["animations"]
        player = pack_check.load_json(str(ROOT / "animations/player.animation.json"))["animations"]
        neutral = evaluate_player(PLAYER_PATHS[0])
        for bone in (
            fp["animation.player.first_person.melee_spear_use"]["bones"]["rightitem"],
            fp["animation.player.first_person.melee_spear_attack"]["bones"]["rightitem"],
            humanoid["animation.humanoid.melee_spear_use"]["bones"]["rightitem"],
            player["animation.player.melee_spear_attack"]["bones"]["rightitem"],
        ):
            actual = [evaluate_expression(value, neutral) for value in bone["position"]]
            assert_vector(self, actual, (0.0, 0.0, 0.0))
        finished = evaluate_player(PLAYER_PATHS[0], attack_time=1.0)
        attack_bone = player["animation.player.melee_spear_attack"]["bones"]["rightitem"]
        assert_vector(self, [evaluate_expression(value, finished) for value in attack_bone["position"]], (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
