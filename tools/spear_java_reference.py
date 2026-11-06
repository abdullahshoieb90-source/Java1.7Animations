#!/usr/bin/env python3
"""Dependency-free reference math for Minecraft Java 1.21.11 spear animations.

The functions mirror SpearAnimations.java and the two PoseStack call sites. They
are test/reference code only; this module is excluded from .mcpack builds.
"""

from __future__ import annotations

import math


FORWARD_MOVEMENT = 0.38
ATTACK_RAISE_END = 0.05
ATTACK_THRUST_END = 0.2
ATTACK_RECOVER_START = 0.4


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def progress(value, start, end):
    return clamp((value - start) / (end - start))


def in_quad(t):
    return t * t


def in_back(t):
    return t * t * (2.70158 * t - 1.70158)


def out_back(t):
    return 1.0 + 2.70158 * (t - 1.0) ** 3 + 1.70158 * (t - 1.0) ** 2


def out_cubic(t):
    return 1.0 - (1.0 - t) ** 3


def out_quart(t):
    return 1.0 - (1.0 - t) ** 4


def in_out_sine(t):
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def in_out_expo(t):
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    if t < 0.5:
        return 2.0 ** (20.0 * t - 10.0) / 2.0
    return (2.0 - 2.0 ** (-20.0 * t + 10.0)) / 2.0


def out_circ(t):
    return math.sqrt(max(0.0, 1.0 - (t - 1.0) ** 2))


def in_circ(t):
    return 1.0 - math.sqrt(max(0.0, 1.0 - t * t))


def in_out_back(t):
    if t < 0.5:
        return 4.0 * t * t * (7.189819 * t - 2.5949094) / 2.0
    x = 2.0 * t - 2.0
    return (x * x * (3.5949094 * x + 2.5949094) + 2.0) / 2.0


def in_out_elastic(t):
    if t == 0.0 or t == 1.0:
        return t
    wave = math.sin((20.0 * t - 11.125) * 1.3962634801864624)
    if t < 0.5:
        return -(2.0 ** (20.0 * t - 10.0) * wave) / 2.0
    return 2.0 ** (-20.0 * t + 10.0) * wave / 2.0 + 1.0


def use_params(ticks, delay, dismount, knockback, damage):
    """Return SpearAnimations.UseParams for one kinetic-weapon tier."""
    finish_raise = delay
    finish_sway = finish_raise + dismount
    start_sway = finish_sway - 20.0
    finish_lower = finish_raise + knockback
    start_lower = finish_lower - 40.0
    finish_raise_back = finish_raise + damage

    raise_progress = progress(ticks, 0.0, finish_raise)
    sway_progress = progress(ticks, start_sway, start_lower)
    lower = out_cubic(in_out_elastic(progress(ticks - 20.0, start_lower, finish_lower)))
    raise_back = progress(ticks, finish_raise_back - 5.0, finish_raise_back)
    intensity = 2.0 * out_circ(sway_progress) - 2.0 * in_circ(raise_back)
    return {
        "raise": raise_progress,
        "start": progress(raise_progress, 0.0, 0.5),
        "middle": progress(raise_progress, 0.5, 0.8),
        "end": progress(raise_progress, 0.8, 1.0),
        "sway": sway_progress,
        "lower": lower,
        "back": raise_back,
        "intensity": intensity,
        "slow": math.sin(math.radians(ticks * 19.0)) * intensity,
        "fast": math.sin(math.radians(ticks * 30.0)) * intensity,
    }


def attack_params(attack_time):
    raise_scale = in_out_sine(progress(attack_time, 0.0, ATTACK_RAISE_END))
    thrust_progress = progress(attack_time, ATTACK_RAISE_END, ATTACK_THRUST_END)
    return {
        "raise": raise_scale,
        "thrust": in_quad(thrust_progress),
        "fp_thrust": out_back(thrust_progress),
        "recover": in_out_expo(progress(attack_time, ATTACK_RECOVER_START, 1.0)),
    }


def hit_feedback(ticks):
    return 0.4 * (
        out_quart(progress(ticks, 1.0, 3.0))
        - in_out_sine(progress(ticks, 3.0, 10.0))
    )


def third_person_hand_base(head_pitch, swim_amount):
    """Pre-clamp X rotation from thirdPersonHandUse, in degrees."""
    return -90.0 + math.degrees(0.8) + head_pitch - 55.0 * clamp(swim_amount)


def third_person_use_arm(params):
    return {
        "x": (
            -40.0 * params["start"]
            + 30.0 * params["middle"]
            - 20.0 * params["end"]
            + 20.0 * params["lower"]
            + 10.0 * params["back"]
            + 0.6 * params["slow"]
        ),
        "y": -params["fast"],
        "z": -0.5 * params["slow"],
    }


def third_person_item(params, attack, hit, side=1):
    raise_scale = params["raise"]
    thrust = attack["thrust"]
    recover = attack["recover"]
    return {
        "translation_y": 16.0 * (
            -FORWARD_MOVEMENT * (in_back(raise_scale) - params["back"]) + hit
        ),
        "rotation_x": 70.0 * (raise_scale - params["back"]) - 40.0 * (thrust - recover),
        # Bedrock's converted rightitem Z corresponds to Java's YP rotation.
        "rotation_z": -side * 90.0 * (
            raise_scale - params["sway"] + 3.0 * recover + thrust
        ),
    }


def third_person_attack_item(attack):
    delta = attack["thrust"] - attack["recover"]
    return {
        "rotation_x": 70.0 * delta,
        "forward": -16.0 * FORWARD_MOVEMENT * delta,
    }


def _rx(degrees):
    c = math.cos(math.radians(degrees))
    s = math.sin(math.radians(degrees))
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def _ry(degrees):
    c = math.cos(math.radians(degrees))
    s = math.sin(math.radians(degrees))
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def _mat_vec(matrix, vector):
    return tuple(sum(row[i] * vector[i] for i in range(3)) for row in matrix)


def _add(*vectors):
    return tuple(sum(values) for values in zip(*vectors))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _around_origin(matrix, pivot):
    return _sub(pivot, _mat_vec(matrix, pivot))


def _fp_coordinates(vector):
    """Convert Java first-person blocks to the Bedrock rightitem basis."""
    x, y, z = vector
    return (16.0 * x, 16.0 * y, -16.0 * z)


def first_person_use(params, hit, side=1):
    """Reference firstPersonUse PoseStack result, in Bedrock coordinates."""
    translation = (
        side * (
            params["raise"] * 0.15
            + params["end"] * -0.05
            + params["sway"] * -0.1
            + params["slow"] * 0.005
        ),
        params["raise"] * -0.075 + params["middle"] * 0.075 + params["fast"] * 0.01,
        params["start"] * 0.05 + params["end"] * -0.05 + params["slow"] * 0.005,
    )
    java_x = (
        -65.0 * in_out_back(params["raise"])
        - 35.0 * params["lower"]
        + 100.0 * params["back"]
        - 0.5 * params["fast"]
    )
    axis_y_n = side * (
        -90.0 * progress(params["raise"], 0.5, 0.55)
        + 90.0 * params["sway"]
        + 2.0 * params["slow"]
    )
    java_y = -axis_y_n
    r1 = _rx(java_x)
    r2 = _ry(java_y)
    pivot1 = (0.0, 0.1, 0.0)
    pivot2 = (side * 0.15, 0.0, 0.0)
    hit_translation = (0.0, -hit, 0.0)

    # PoseStack post-multiplication: initial translation is outside the rotations;
    # the second pivot compensation and final translation use prior linear parts.
    origin = _add(
        translation,
        _around_origin(r1, pivot1),
        _mat_vec(r1, _around_origin(r2, pivot2)),
        _mat_vec(r1, _mat_vec(r2, hit_translation)),
    )
    return {
        "position": _fp_coordinates(origin),
        "rotation_x": -java_x,
        "rotation_y": -java_y,
    }


def first_person_attack(attack, side=1):
    """Reference firstPersonAttack PoseStack result, in Bedrock coordinates."""
    thrust = attack["fp_thrust"]
    recover = attack["recover"]
    translation = (
        side * 0.1 * (attack["raise"] - thrust),
        -0.075 * (attack["raise"] - recover),
        0.65 * (attack["raise"] - thrust),
    )
    java_x = -70.0 * (attack["raise"] - recover)
    rotation = _rx(java_x)
    local_recovery = (0.0, 0.0, -0.25 * (recover - thrust))
    origin = _add(translation, _mat_vec(rotation, local_recovery))
    return {
        "position": _fp_coordinates(origin),
        "rotation_x": -java_x,
    }
