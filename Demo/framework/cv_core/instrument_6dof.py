from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class InstrumentPoseMeasurement:
    position: list[float]
    rotation: list[float]  # quat [x, y, z, w]
    confidence: float
    source: str
    reprojection_error: float
    rvec: Optional[np.ndarray] = None  # Rotation vector for geometry transformation
    tvec: Optional[np.ndarray] = None  # Translation vector for geometry transformation


class InstrumentPoseEstimator:
    """Estimate rigid instrument 6DoF using solvePnP."""

    _DEFAULT_MODEL_POINTS: Dict[str, Dict[str, list[float]]] = {
        "violin": {
            "center": [0.0, 0.0, 0.0],
            "neck_end": [0.33, 0.0, 0.0],
            "body_end": [0.0, -0.14, 0.0],
            "chin_anchor": [-0.05, 0.08, 0.0],
        },
    }

    def __init__(self, mode: str = "pnp", profiles: Optional[Dict[str, Any]] = None) -> None:
        self.mode = mode
        self.profiles = profiles or {}

    def estimate(
        self,
        frame_bgr: np.ndarray,
        intrinsics: Dict[str, float],
        instrument_name: str,
        hint_pose: Optional[Dict[str, Any]] = None,
    ) -> Optional[InstrumentPoseMeasurement]:
        if self.mode != "pnp":
            raise ValueError(f"Unsupported tracking mode: {self.mode}")
        return self._estimate_pnp(frame_bgr, intrinsics, instrument_name, hint_pose)

    def _estimate_pnp(
        self,
        frame_bgr: np.ndarray,
        intrinsics: Dict[str, float],
        instrument_name: str,
        hint_pose: Optional[Dict[str, Any]],
    ) -> Optional[InstrumentPoseMeasurement]:
        if hint_pose is None:
            return None

        object_points, image_points = self._build_correspondences(hint_pose, instrument_name, frame_bgr.shape[1], frame_bgr.shape[0])
        if object_points is None or image_points is None:
            return None

        k = np.array(
            [
                [intrinsics["fx"], 0.0, intrinsics["cx"]],
                [0.0, intrinsics["fy"], intrinsics["cy"]],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        d = np.zeros((4, 1), dtype=np.float64)

        ok, rvec, tvec, inliers = cv2.solvePnPRansac(
            object_points,
            image_points,
            k,
            d,
            flags=cv2.SOLVEPNP_EPNP,
            reprojectionError=4.0,
            confidence=0.98,
            iterationsCount=80,
        )
        if not ok:
            return None

        proj, _ = cv2.projectPoints(object_points, rvec, tvec, k, d)
        proj = proj.reshape(-1, 2)
        err = float(np.mean(np.linalg.norm(proj - image_points, axis=1)))
        inlier_ratio = float(len(inliers) / len(object_points)) if inliers is not None and len(object_points) > 0 else 0.0
        confidence = float(np.clip(inlier_ratio * np.exp(-err / 10.0), 0.0, 1.0))

        quat = self._quat_from_rvec(rvec)
        return InstrumentPoseMeasurement(
            position=tvec.reshape(3).astype(np.float32).tolist(),
            rotation=quat,
            confidence=confidence,
            source="pnp",
            reprojection_error=err,
            rvec=rvec.astype(np.float32),
            tvec=tvec.reshape(3).astype(np.float32),
        )

    def _build_correspondences(
        self,
        hint_pose: Dict[str, Any],
        instrument_name: str,
        width: int,
        height: int,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        model_points = self._get_model_points(instrument_name)
        if not model_points:
            return None, None

        key_specs = [(k, v) for k, v in model_points.items()]

        obj = []
        img = []
        for key, model_pt in key_specs:
            v = hint_pose.get(key)
            if not isinstance(v, (list, tuple)) or len(v) < 2:
                continue
            u = float(v[0]) * width
            vv = float(v[1]) * height
            obj.append(model_pt)
            img.append([u, vv])

        if len(obj) < 4:
            return None, None

        return np.asarray(obj, dtype=np.float64), np.asarray(img, dtype=np.float64)

    def _get_model_points(self, instrument_name: str) -> Dict[str, list[float]]:
        defaults = self._DEFAULT_MODEL_POINTS.get(instrument_name, {})
        if not defaults:
            return {}

        instrument_profile = self.profiles.get(instrument_name, {}) if isinstance(self.profiles, dict) else {}
        if not isinstance(instrument_profile, dict):
            return dict(defaults)

        if instrument_name != "violin":
            return dict(defaults)

        profile_pts = instrument_profile.get("pnp_keypoints", {})
        if not isinstance(profile_pts, dict):
            return dict(defaults)

        merged: Dict[str, list[float]] = {}
        for key, fallback in defaults.items():
            candidate = profile_pts.get(key)
            if self._is_valid_xyz(candidate):
                merged[key] = [float(candidate[0]), float(candidate[1]), float(candidate[2])]
            else:
                merged[key] = list(fallback)

        return merged

    @staticmethod
    def _is_valid_xyz(v: Any) -> bool:
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            return False
        try:
            float(v[0])
            float(v[1])
            float(v[2])
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def _quat_from_rvec(rvec: np.ndarray) -> list[float]:
        rot, _ = cv2.Rodrigues(rvec)
        trace = float(np.trace(rot))
        if trace > 0.0:
            s = np.sqrt(trace + 1.0) * 2.0
            qw = 0.25 * s
            qx = (rot[2, 1] - rot[1, 2]) / s
            qy = (rot[0, 2] - rot[2, 0]) / s
            qz = (rot[1, 0] - rot[0, 1]) / s
        elif rot[0, 0] > rot[1, 1] and rot[0, 0] > rot[2, 2]:
            s = np.sqrt(1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2]) * 2.0
            qw = (rot[2, 1] - rot[1, 2]) / s
            qx = 0.25 * s
            qy = (rot[0, 1] + rot[1, 0]) / s
            qz = (rot[0, 2] + rot[2, 0]) / s
        elif rot[1, 1] > rot[2, 2]:
            s = np.sqrt(1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2]) * 2.0
            qw = (rot[0, 2] - rot[2, 0]) / s
            qx = (rot[0, 1] + rot[1, 0]) / s
            qy = 0.25 * s
            qz = (rot[1, 2] + rot[2, 1]) / s
        else:
            s = np.sqrt(1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1]) * 2.0
            qw = (rot[1, 0] - rot[0, 1]) / s
            qx = (rot[0, 2] + rot[2, 0]) / s
            qy = (rot[1, 2] + rot[2, 1]) / s
            qz = 0.25 * s

        q = np.array([qx, qy, qz, qw], dtype=np.float32)
        n = np.linalg.norm(q)
        if n < 1e-8:
            return [0.0, 0.0, 0.0, 1.0]
        q /= n
        return q.tolist()
