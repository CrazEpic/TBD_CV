from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Deque, Dict, Optional

import numpy as np

from .hand_tracking import HolisticState


class _ScalarKalman:
    def __init__(self, q: float = 1e-4, r: float = 1e-2) -> None:
        self.q = q
        self.r = r
        self.x = 0.0
        self.p = 1.0
        self.initialized = False

    def update(self, measurement: float) -> float:
        if not self.initialized:
            self.x = measurement
            self.initialized = True
            return measurement

        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x = self.x + k * (measurement - self.x)
        self.p = (1.0 - k) * self.p
        return self.x


class TemporalSmoother:
    """Applies moving average smoothing and optional Kalman post-filtering."""

    def __init__(self, window_size: int = 5, use_kalman: bool = False) -> None:
        self.window_size = max(window_size, 1)
        self.use_kalman = use_kalman
        self._buffers: Dict[str, Deque[np.ndarray]] = {
            "pose": deque(maxlen=self.window_size),
            "left": deque(maxlen=self.window_size),
            "right": deque(maxlen=self.window_size),
            "face": deque(maxlen=self.window_size),
        }
        self._kalman: Dict[str, Optional[list]] = {"pose": None, "left": None, "right": None, "face": None}

    def smooth(self, state: HolisticState) -> HolisticState:
        """Smooth pose and hand landmarks (temporal filtering)."""
        pose = self._smooth_pose(state.pose)
        left = self._smooth_hand("left", state.left_hand)
        right = self._smooth_hand("right", state.right_hand)
        face = self._smooth_hand("face", state.face)
        return replace(state, pose=pose, left_hand=left, right_hand=right, face=face)

    def _smooth_pose(self, points):
        """Smooth pose landmarks (33 points with visibility)."""
        if points is None:
            return None

        arr = np.asarray(points, dtype=np.float32)
        self._buffers["pose"].append(arr)
        stacked = np.stack(self._buffers["pose"], axis=0)
        smoothed = np.mean(stacked, axis=0)
        return smoothed.tolist()

    def _smooth_hand(self, side: str, points):
        if points is None:
            self._buffers[side].clear()
            self._kalman[side] = None
            return None

        arr = np.asarray(points, dtype=np.float32)
        self._buffers[side].append(arr)
        stacked = np.stack(self._buffers[side], axis=0)
        smoothed = np.mean(stacked, axis=0)

        if not self.use_kalman:
            return smoothed.tolist()

        if self._kalman[side] is None:
            self._kalman[side] = [_ScalarKalman() for _ in range(smoothed.size)]

        filtered = smoothed.reshape(-1).copy()
        for i, val in enumerate(filtered):
            filtered[i] = self._kalman[side][i].update(float(val))

        return filtered.reshape(smoothed.shape).tolist()
