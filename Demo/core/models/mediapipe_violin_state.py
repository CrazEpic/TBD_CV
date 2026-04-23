from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict

from core.models.mediapipe_holistic_state import (
    HolisticState,
    PoseLandmark,
)
from core.models.violin import ViolinProfile


Vec3 = tuple[float, float, float]


# =========================
# Output State
# =========================
class ViolinState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: Vec3
    neck_dir_3d: Vec3
    neck_dir_2d: tuple[float, float]
    right_dir_2d: tuple[float, float]
    up_dir_2d: tuple[float, float]
    model_scale: float
    confidence: float

    def transform_local_xz(
        self,
        point_local: tuple[float, float, float],
        origin_local: tuple[float, float, float],
    ) -> tuple[float, float]:
        dx = (point_local[0] - origin_local[0]) * self.model_scale
        dz = (point_local[2] - origin_local[2]) * self.model_scale

        x = self.anchor[0] + self.right_dir_2d[0] * dx + self.neck_dir_2d[0] * dz
        y = self.anchor[1] + self.right_dir_2d[1] * dx + self.neck_dir_2d[1] * dz
        return (x, y)


# =========================
# Estimator
# =========================
class ViolinStateEstimator:
    """Real-time stable violin pose estimator (Option C)."""

    # Debug constants for legacy anchor estimation
    JAW_BLEND_MOUTH = 0.5
    NECK_SHIFT_TOWARD_SHOULDER = 0.35

    def __init__(self) -> None:
        self._prev_anchor: Optional[Vec3] = None
        self._prev_dir: Optional[tuple[float, float]] = None

    def estimate(
        self,
        holistic: HolisticState,
        profile: ViolinProfile,
    ) -> Optional[ViolinState]:

        # --- Landmarks ---
        shoulder_l = holistic.get_pose_landmark(PoseLandmark.LEFT_SHOULDER)
        shoulder_r = holistic.get_pose_landmark(PoseLandmark.RIGHT_SHOULDER)
        wrist_l = holistic.get_pose_landmark(PoseLandmark.LEFT_WRIST)
        hip_l = holistic.get_pose_landmark(PoseLandmark.LEFT_HIP)
        hip_r = holistic.get_pose_landmark(PoseLandmark.RIGHT_HIP)

        if not (shoulder_l and shoulder_r and wrist_l and hip_l and hip_r):
            return None

        shoulder_left = _pt(shoulder_l)
        shoulder_right = _pt(shoulder_r)
        wrist_left = _pt(wrist_l)
        hip_left = _pt(hip_l)
        hip_right = _pt(hip_r)

        # =========================
        # 1) Anchor: local (0,0,0) at body neck base
        # =========================
        anchor = _mid(shoulder_left, shoulder_right)

        # Smooth anchor
        if self._prev_anchor is not None:
            alpha = 0.2
            anchor = _lerp(self._prev_anchor, anchor, alpha)

        self._prev_anchor = anchor

        # =========================
        # 2) Forward/neck direction: left shoulder -> left wrist
        # =========================
        v_fwd = _normalize(_sub(wrist_left, shoulder_left))
        if _length(v_fwd) < 1e-6:
            return None

        # =========================
        # 3) Base orientation from torso
        # =========================
        shoulder_mid = _mid(shoulder_left, shoulder_right)
        hip_mid = _mid(hip_left, hip_right)

        torso_up = _normalize(_sub(shoulder_mid, hip_mid))
        if _length(torso_up) < 1e-6:
            return None

        v_right = _normalize(_cross(v_fwd, torso_up))
        if _length(v_right) < 1e-6:
            return None

        v_up = _normalize(_cross(v_right, v_fwd))

        # =========================
        # 4) Tilt +30 degrees toward local +X (right)
        # =========================
        tilt_rad = math.radians(30.0)
        v_up_tilted = _normalize(_add(_scale(v_up, math.cos(tilt_rad)), _scale(v_right, math.sin(tilt_rad))))
        v_right_tilted = _normalize(_cross(v_fwd, v_up_tilted))

        # Project basis to image plane once for render state.
        # +Z is defined in 3D by shoulder->wrist and then projected for drawing.
        neck_dir_2d = _normalize_2d(_project_to_2d(v_fwd))
        right_dir_2d = _normalize_2d(_project_to_2d(v_right_tilted))
        up_dir_2d = _normalize_2d(_project_to_2d(v_up_tilted))


        # =========================
        # 6. CONFIDENCE
        # =========================
        left_hand_conf = float(holistic.confidences.get("left_hand", 0.0))
        pose_conf = float(holistic.confidences.get("pose", 0.0))

        confidence = max(0.0, min(1.0, 0.6 * pose_conf + 0.4 * left_hand_conf))

        return ViolinState(
            anchor=anchor,
            neck_dir_3d=v_fwd,
            neck_dir_2d=neck_dir_2d,
            right_dir_2d=right_dir_2d,
            up_dir_2d=up_dir_2d,
            model_scale=1.0,
            confidence=confidence,
        )


# =========================
# Math helpers
# =========================
def _pt(p) -> Vec3:
    return (float(p.x), float(p.y), float(p.z))


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _length(v: Vec3) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _normalize(v: Vec3) -> Vec3:
    length = _length(v)
    if length < 1e-6:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _normalize_2d(v: tuple[float, float]) -> tuple[float, float]:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1])
    if length < 1e-6:
        return (0.0, -1.0)
    return (v[0] / length, v[1] / length)


def _mid(a: Vec3, b: Vec3) -> Vec3:
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def _cross(a: Vec3, b: Vec3) -> Vec3:
    """Compute cross product of two 3D vectors."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    """Compute dot product of two 3D vectors."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _project_to_2d(v: Vec3) -> tuple[float, float]:
    """Project a 3D vector to 2D (x, y components)."""
    return (v[0], v[1])
