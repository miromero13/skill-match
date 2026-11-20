"""Synthetic 3D skeletons -> pose signatures, so engine tests do not depend on videos of real people.

A tiny forward-kinematics stick figure produces MediaPipe-like world landmarks (y down, person facing -z);
the engine's own ``landmarks_to_features`` turns them into the stored signature format.
"""
from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from app.skill_validation.pose import SAMPLE_FPS, build_signature, landmarks_to_features

Pose = dict[str, float]  # joint angles in degrees

STAND: Pose = {
    "trunk": 0.0, "l_sh_flex": 0.0, "r_sh_flex": 0.0, "l_sh_abd": 10.0, "r_sh_abd": 10.0,
    "l_elbow": 10.0, "r_elbow": 10.0, "l_hip_flex": 0.0, "r_hip_flex": 0.0, "l_hip_abd": 3.0,
    "r_hip_abd": 3.0, "l_knee": 5.0, "r_knee": 5.0,
}


def _rot_x(deg: float) -> np.ndarray:
    a = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])


def _rot_z(deg: float) -> np.ndarray:
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])


DOWN = np.array([0.0, 1.0, 0.0])


def skeleton(p: Pose) -> np.ndarray:
    """33x3 world landmarks for joint angles ``p`` (flexion raises a limb forward, toward -z)."""
    lm = np.zeros((33, 3))
    trunk = _rot_x(p["trunk"])  # bend forward
    up = trunk @ np.array([0.0, -1.0, 0.0])
    for side, sign in (("l", 1.0), ("r", -1.0)):
        hip = np.array([0.1 * sign, 0.0, 0.0])
        shoulder = trunk @ np.array([0.18 * sign, -0.5, 0.0])
        arm = trunk @ _rot_z(-sign * p[f"{side}_sh_abd"]) @ _rot_x(p[f"{side}_sh_flex"]) @ DOWN
        elbow = shoulder + 0.28 * arm
        fore = trunk @ _rot_z(-sign * p[f"{side}_sh_abd"]) @ _rot_x(p[f"{side}_sh_flex"] + p[f"{side}_elbow"]) @ DOWN
        wrist = elbow + 0.25 * fore
        thigh = _rot_z(-sign * p[f"{side}_hip_abd"]) @ _rot_x(p[f"{side}_hip_flex"]) @ DOWN
        knee = hip + 0.42 * thigh
        shank = _rot_z(-sign * p[f"{side}_hip_abd"]) @ _rot_x(p[f"{side}_hip_flex"] - p[f"{side}_knee"]) @ DOWN
        ankle = knee + 0.4 * shank
        foot = ankle + 0.15 * (_rot_x(p[f"{side}_hip_flex"] - p[f"{side}_knee"] + 90.0) @ DOWN)
        idx = {"l": (11, 13, 15, 23, 25, 27, 31), "r": (12, 14, 16, 24, 26, 28, 32)}[side]
        for i, point in zip(idx, (shoulder, elbow, wrist, hip, knee, ankle, foot)):
            lm[i] = point
    lm[0] = (lm[11] + lm[12]) / 2 + 0.25 * up
    return lm


def _wave(t: float) -> float:
    """0 -> 1 -> 0 over one cycle, smooth."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * t)


def juggle(t: float) -> Pose:
    p = dict(STAND)
    k = _wave(t)
    p.update(r_hip_flex=65 * k, r_knee=10 + 55 * k, l_knee=12, l_sh_abd=25 + 10 * k, r_sh_abd=25 + 10 * k,
             l_elbow=30, r_elbow=30, trunk=5 + 5 * k)
    return p


def squat(t: float) -> Pose:
    p = dict(STAND)
    k = _wave(t)
    p.update(l_hip_flex=95 * k, r_hip_flex=95 * k, l_knee=5 + 110 * k, r_knee=5 + 110 * k,
             l_sh_flex=90 * k, r_sh_flex=90 * k, trunk=35 * k)
    return p


def jumping_jack(t: float) -> Pose:
    p = dict(STAND)
    k = _wave(t)
    p.update(l_sh_abd=10 + 160 * k, r_sh_abd=10 + 160 * k, l_hip_abd=3 + 22 * k, r_hip_abd=3 + 22 * k)
    return p


def right_arm_wave(t: float) -> Pose:
    p = dict(STAND)
    p.update(r_sh_abd=150, r_elbow=40 + 60 * _wave(2 * t))
    return p


def static(t: float) -> Pose:
    return dict(STAND)


def mirrored(motion: Callable[[float], Pose]) -> Callable[[float], Pose]:
    def run(t: float) -> Pose:
        p = motion(t)
        return {(k.replace("l_", "x_", 1).replace("r_", "l_", 1).replace("x_", "r_", 1)
                 if k[:2] in ("l_", "r_") else k): v for k, v in p.items()}
    return run


def signature(
    motion: Callable[[float], Pose], seconds: float = 6.0, cycle_seconds: float = 2.0, noise_deg: float = 0.0,
    lead_in_seconds: float = 0.0, seed: int = 0, view_yaw_deg: float = 0.0, visibility: float = 0.95,
    missing_every: int = 0,
) -> dict:
    """Pose block (same format ``analyze_video`` stores) for ``motion`` at SAMPLE_FPS.

    ``view_yaw_deg`` rotates the whole body (the world landmarks a different camera would see),
    ``noise_deg`` jitters landmark positions, ``missing_every`` drops every n-th frame (nobody detected).
    """
    rng = np.random.default_rng(seed)
    rows = []
    total = int(round((seconds + lead_in_seconds) * SAMPLE_FPS))
    yaw = np.array([[math.cos(math.radians(view_yaw_deg)), 0, math.sin(math.radians(view_yaw_deg))],
                    [0, 1, 0], [-math.sin(math.radians(view_yaw_deg)), 0, math.cos(math.radians(view_yaw_deg))]])
    for i in range(total):
        t = i / SAMPLE_FPS - lead_in_seconds
        p = STAND if t < 0 else motion((t / cycle_seconds) % 1.0)
        lm = skeleton(p) @ yaw.T
        if noise_deg:
            lm = lm + rng.normal(0, 0.003 * noise_deg, lm.shape)
        if missing_every and i % missing_every == missing_every - 1:
            rows.append(None)
            continue
        rows.append(landmarks_to_features(lm, np.full(33, visibility)))
    return build_signature(rows, SAMPLE_FPS)


def analysis(pose: dict | None, *, ball: dict | None = None, duration: float = 6.0) -> dict:
    """A complete ``analyze_video``-shaped dict around a pose block."""
    from app.skill_validation import ENGINE_VERSION

    return {
        "engine_version": ENGINE_VERSION,
        "readable": True,
        "duration_seconds": duration,
        "frames_analyzed": pose["frames_sampled"] if pose else 0,
        "pose": pose,
        "pose_status": "ok" if pose else "model_unavailable",
        "ball": ball,
        "ball_status": "ok" if ball else "not_requested",
        "notes": [],
    }


def shallow_squat(t: float, depth: float = 0.6) -> Pose:
    """A beginner's squat: less depth, arms barely raised, more forward lean."""
    p = dict(STAND)
    k = _wave(t)
    p.update(l_hip_flex=95 * depth * k, r_hip_flex=95 * depth * k, l_knee=5 + 110 * depth * k,
             r_knee=5 + 110 * depth * k, l_sh_flex=30 * k, r_sh_flex=30 * k, trunk=45 * k)
    return p
