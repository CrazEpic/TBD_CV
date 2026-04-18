from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

from .hand_tracking import HolisticState


FINGER_CHAINS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


class FeatureExtractor:
    """Shared middleware that converts hand landmarks to reusable features."""

    def __init__(self) -> None:
        self._prev_wrist = {"left": None, "right": None}
        self._prev_time = {"left": None, "right": None}

    def extract(self, state: HolisticState) -> Dict[str, dict]:
        """Extract shared pose + hand features for instrument modules."""
        return {
            "timestamp": state.timestamp,
            "pose": self._extract_pose(state.pose),
            "left": self._extract_hand("left", state.left_hand, state.timestamp),
            "right": self._extract_hand("right", state.right_hand, state.timestamp),
        }

    def _extract_pose(self, points) -> Optional[dict]:
        if points is None:
            return None

        pts = np.asarray(points, dtype=np.float32)
        pts_xyz = pts[:, :3]

        left_shoulder = pts_xyz[11]
        right_shoulder = pts_xyz[12]
        left_ear = pts_xyz[7]
        right_ear = pts_xyz[8]
        nose = pts_xyz[0]
        left_elbow = pts_xyz[13]
        right_elbow = pts_xyz[14]
        left_wrist = pts_xyz[15]
        right_wrist = pts_xyz[16]
        left_hip = pts_xyz[23]
        right_hip = pts_xyz[24]
        mouth_left = pts_xyz[9]
        mouth_right = pts_xyz[10]

        shoulder_center = ((left_shoulder + right_shoulder) * 0.5).tolist()
        hip_center = ((left_hip + right_hip) * 0.5).tolist()

        body_up = self._normalize((np.asarray(shoulder_center) - np.asarray(hip_center)).astype(np.float32))
        shoulder_line = self._normalize((right_shoulder - left_shoulder).astype(np.float32))
        body_forward = self._normalize(np.cross(shoulder_line, body_up))

        return {
            "landmarks": pts.tolist(),
            "joints": {
                "left_shoulder": left_shoulder.tolist(),
                "right_shoulder": right_shoulder.tolist(),
                "left_ear": left_ear.tolist(),
                "right_ear": right_ear.tolist(),
                "nose": nose.tolist(),
                "left_elbow": left_elbow.tolist(),
                "right_elbow": right_elbow.tolist(),
                "left_wrist": left_wrist.tolist(),
                "right_wrist": right_wrist.tolist(),
                "left_hip": left_hip.tolist(),
                "right_hip": right_hip.tolist(),
                "mouth_left": mouth_left.tolist(),
                "mouth_right": mouth_right.tolist(),
            },
            "torso": {
                "shoulder_center": shoulder_center,
                "hip_center": hip_center,
                "body_up": body_up.tolist(),
                "body_forward": body_forward.tolist(),
            },
        }

    def _extract_hand(self, side: str, points, timestamp: float) -> Optional[dict]:
        if points is None:
            self._prev_wrist[side] = None
            self._prev_time[side] = None
            return None

        pts = np.asarray(points, dtype=np.float32)

        fingers = {}
        for finger_name, chain in FINGER_CHAINS.items():
            a, b, c, d = chain
            pip_angle = self._joint_angle(pts[a], pts[b], pts[c])
            dip_angle = self._joint_angle(pts[b], pts[c], pts[d])
            extension = float(self._distance(pts[0], pts[d]) > self._distance(pts[0], pts[b]))

            fingers[finger_name] = {
                "pip_angle_deg": pip_angle,
                "dip_angle_deg": dip_angle,
                "extended": bool(extension > 0.5),
                "curled_score": float(1.0 - min(pip_angle, 180.0) / 180.0),
            }

        palm_normal = self._normalize(np.cross(pts[5] - pts[0], pts[17] - pts[0]))
        hand_forward = self._normalize(pts[9] - pts[0])

        prev_wrist = self._prev_wrist[side]
        prev_time = self._prev_time[side]
        if prev_wrist is None or prev_time is None:
            wrist_velocity = np.zeros(3, dtype=np.float32)
        else:
            dt = max(timestamp - prev_time, 1e-5)
            wrist_velocity = (pts[0] - prev_wrist) / dt

        self._prev_wrist[side] = pts[0].copy()
        self._prev_time[side] = timestamp

        relative_distances = {
            "thumb_index_tip": self._distance(pts[4], pts[8]),
            "index_middle_tip": self._distance(pts[8], pts[12]),
            "middle_ring_tip": self._distance(pts[12], pts[16]),
            "ring_pinky_tip": self._distance(pts[16], pts[20]),
        }

        return {
            "fingers": fingers,
            "landmarks": pts.tolist(),
            "tips": {
                "thumb": pts[4].tolist(),
                "index": pts[8].tolist(),
                "middle": pts[12].tolist(),
                "ring": pts[16].tolist(),
                "pinky": pts[20].tolist(),
            },
            "hand_pose": {
                "wrist": pts[0].tolist(),
                "palm_normal": palm_normal.tolist(),
                "hand_forward": hand_forward.tolist(),
            },
            "motion": {
                "wrist_velocity": wrist_velocity.tolist(),
                "wrist_speed": float(np.linalg.norm(wrist_velocity)),
            },
            "relative_distances": relative_distances,
        }

    @staticmethod
    def _distance(a, b) -> float:
        return float(np.linalg.norm(a - b))

    @staticmethod
    def _normalize(v):
        norm = np.linalg.norm(v)
        if norm < 1e-8:
            return np.zeros_like(v)
        return v / norm

    @staticmethod
    def _joint_angle(a, b, c) -> float:
        ba = a - b
        bc = c - b
        denom = np.linalg.norm(ba) * np.linalg.norm(bc)
        if denom < 1e-8:
            return 0.0
        cosine = float(np.clip(np.dot(ba, bc) / denom, -1.0, 1.0))
        return math.degrees(math.acos(cosine))
