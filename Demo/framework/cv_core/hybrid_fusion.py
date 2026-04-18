from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class JointMeasurement:
    position: list[float]
    rotation: list[float]
    confidence: float


@dataclass
class EntityState:
    position: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray
    rotation: np.ndarray
    angular_velocity: np.ndarray
    confidence: float


class HybridFusionEngine:
    """Confidence-weighted temporal fusion for human joints and instrument 6DoF."""

    HUMAN_BONE_PAIRS = [
        ("pose_11", "pose_13"),
        ("pose_13", "pose_15"),
        ("pose_12", "pose_14"),
        ("pose_14", "pose_16"),
        ("pose_23", "pose_25"),
        ("pose_25", "pose_27"),
        ("pose_24", "pose_26"),
        ("pose_26", "pose_28"),
    ]

    def __init__(
        self,
        base_gain: float = 0.45,
        confidence_threshold: float = 0.2,
        pos_smoothing_alpha: float = 0.75,
        max_speed: float = 6.0,
        max_angular_speed: float = 14.0,
    ) -> None:
        self.base_gain = base_gain
        self.confidence_threshold = confidence_threshold
        self.pos_smoothing_alpha = pos_smoothing_alpha
        self.max_speed = max_speed
        self.max_angular_speed = max_angular_speed

        self._human_states: Dict[str, EntityState] = {}
        self._instrument_state: Optional[EntityState] = None
        self._bone_lengths: Dict[tuple[str, str], float] = {}

    def update(
        self,
        dt: float,
        human_measurements: Dict[str, JointMeasurement],
        instrument_measurement: Optional[JointMeasurement],
        instrument_name: str,
    ) -> Dict[str, Any]:
        dt = max(dt, 1e-3)

        for key in human_measurements.keys():
            if key not in self._human_states:
                self._human_states[key] = self._init_state(human_measurements[key])

        if instrument_measurement is not None and self._instrument_state is None:
            self._instrument_state = self._init_state(instrument_measurement)

        for state in self._human_states.values():
            self._predict(state, dt)

        if self._instrument_state is not None:
            self._predict(self._instrument_state, dt)

        for key, meas in human_measurements.items():
            self._update(self._human_states[key], meas, dt)

        if instrument_measurement is not None:
            if self._instrument_state is None:
                self._instrument_state = self._init_state(instrument_measurement)
            self._update(self._instrument_state, instrument_measurement, dt)

        self._enforce_bone_lengths()
        contacts = self._apply_hand_instrument_constraints(instrument_name)

        human_out = {
            key: {
                "position": state.position.astype(np.float32).tolist(),
                "rotation": self._normalize_quat(state.rotation).astype(np.float32).tolist(),
                "confidence": float(state.confidence),
            }
            for key, state in self._human_states.items()
        }

        if self._instrument_state is not None:
            instrument_out = {
                "position": self._instrument_state.position.astype(np.float32).tolist(),
                "rotation": self._normalize_quat(self._instrument_state.rotation).astype(np.float32).tolist(),
                "confidence": float(self._instrument_state.confidence),
            }
        else:
            instrument_out = {
                "position": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "confidence": 0.0,
            }

        return {
            "human_joints": human_out,
            "instrument": instrument_out,
            "contacts": contacts,
        }

    def _init_state(self, meas: JointMeasurement) -> EntityState:
        return EntityState(
            position=np.asarray(meas.position, dtype=np.float32),
            velocity=np.zeros(3, dtype=np.float32),
            acceleration=np.zeros(3, dtype=np.float32),
            rotation=self._normalize_quat(np.asarray(meas.rotation, dtype=np.float32)),
            angular_velocity=np.zeros(3, dtype=np.float32),
            confidence=float(meas.confidence),
        )

    def _predict(self, state: EntityState, dt: float) -> None:
        # Constant-acceleration motion model.
        state.position = state.position + state.velocity * dt + 0.5 * state.acceleration * (dt * dt)
        state.velocity = state.velocity + state.acceleration * dt
        speed = np.linalg.norm(state.velocity)
        if speed > self.max_speed:
            state.velocity *= self.max_speed / max(speed, 1e-8)

        ang_speed = np.linalg.norm(state.angular_velocity)
        if ang_speed > self.max_angular_speed:
            state.angular_velocity *= self.max_angular_speed / max(ang_speed, 1e-8)

        if ang_speed > 1e-6:
            axis = state.angular_velocity / ang_speed
            dq = self._quat_from_axis_angle(axis, ang_speed * dt)
            state.rotation = self._quat_mul(state.rotation, dq)
            state.rotation = self._normalize_quat(state.rotation)

    def _update(self, state: EntityState, meas: JointMeasurement, dt: float) -> None:
        conf = float(np.clip(meas.confidence, 0.0, 1.0))
        state.confidence = 0.9 * state.confidence + 0.1 * conf

        if conf < self.confidence_threshold:
            return

        k = float(np.clip(self.base_gain * conf, 0.02, 0.95))

        measurement_pos = np.asarray(meas.position, dtype=np.float32)
        pred_pos = state.position.copy()
        update_pos = pred_pos + k * (measurement_pos - pred_pos)
        smoothed_pos = self.pos_smoothing_alpha * pred_pos + (1.0 - self.pos_smoothing_alpha) * update_pos

        new_vel = (smoothed_pos - state.position) / dt
        new_acc = (new_vel - state.velocity) / dt

        state.position = smoothed_pos
        state.velocity = new_vel
        state.acceleration = new_acc

        measurement_rot = self._normalize_quat(np.asarray(meas.rotation, dtype=np.float32))
        new_rot = self._quat_slerp(state.rotation, measurement_rot, k)
        delta = self._quat_mul(new_rot, self._quat_conj(state.rotation))
        axis, angle = self._axis_angle_from_quat(delta)
        state.angular_velocity = axis * (angle / dt)
        state.rotation = self._normalize_quat(new_rot)

    def _enforce_bone_lengths(self) -> None:
        for a, b in self.HUMAN_BONE_PAIRS:
            if a not in self._human_states or b not in self._human_states:
                continue

            pa = self._human_states[a].position
            pb = self._human_states[b].position
            d = pb - pa
            dist = float(np.linalg.norm(d))
            if dist < 1e-6:
                continue

            key = (a, b)
            if key not in self._bone_lengths and self._human_states[a].confidence > 0.6 and self._human_states[b].confidence > 0.6:
                self._bone_lengths[key] = dist

            if key not in self._bone_lengths:
                continue

            target_len = self._bone_lengths[key]
            corrected = pa + (d / dist) * target_len
            self._human_states[b].position = 0.75 * pb + 0.25 * corrected

    def _apply_hand_instrument_constraints(self, instrument_name: str) -> Dict[str, Any]:
        if self._instrument_state is None or instrument_name == "none":
            return {}

        left = self._human_states.get("pose_15")
        right = self._human_states.get("pose_16")
        nose = self._human_states.get("pose_0")

        if left is None or right is None:
            return {}

        contacts: Dict[str, Any] = {}
        q = self._normalize_quat(self._instrument_state.rotation)
        p = self._instrument_state.position

        if instrument_name == "flute":
            mouth_offset = np.array([0.05, 0.02, 0.0], dtype=np.float32)
            left_offset = np.array([-0.12, 0.0, 0.0], dtype=np.float32)
            right_offset = np.array([0.24, 0.0, 0.0], dtype=np.float32)

            mouth_target = p + self._rotate_vec(q, mouth_offset)
            left_target = p + self._rotate_vec(q, left_offset)
            right_target = p + self._rotate_vec(q, right_offset)

            left.position = 0.7 * left.position + 0.3 * left_target
            right.position = 0.7 * right.position + 0.3 * right_target
            if nose is not None:
                nose.position = 0.85 * nose.position + 0.15 * mouth_target

            contacts["left_hand_to_flute"] = float(np.linalg.norm(left.position - left_target))
            contacts["right_hand_to_flute"] = float(np.linalg.norm(right.position - right_target))
            contacts["mouth_to_embouchure"] = float(np.linalg.norm((nose.position if nose is not None else mouth_target) - mouth_target))

        else:
            chin_offset = np.array([-0.05, 0.08, 0.0], dtype=np.float32)
            neck_offset = np.array([0.22, 0.0, 0.0], dtype=np.float32)
            bow_offset = np.array([0.0, -0.14, 0.0], dtype=np.float32)

            chin_target = p + self._rotate_vec(q, chin_offset)
            left_target = p + self._rotate_vec(q, neck_offset)
            right_target = p + self._rotate_vec(q, bow_offset)

            left.position = 0.68 * left.position + 0.32 * left_target
            right.position = 0.68 * right.position + 0.32 * right_target
            if nose is not None:
                nose.position = 0.85 * nose.position + 0.15 * chin_target

            contacts["left_hand_to_neck"] = float(np.linalg.norm(left.position - left_target))
            contacts["right_hand_to_bow"] = float(np.linalg.norm(right.position - right_target))
            contacts["chin_to_rest"] = float(np.linalg.norm((nose.position if nose is not None else chin_target) - chin_target))

        return contacts

    @staticmethod
    def _rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        qv = np.array([v[0], v[1], v[2], 0.0], dtype=np.float32)
        return HybridFusionEngine._quat_mul(HybridFusionEngine._quat_mul(q, qv), HybridFusionEngine._quat_conj(q))[:3]

    @staticmethod
    def _normalize_quat(q: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(q)
        if n < 1e-8:
            return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        return q / n

    @staticmethod
    def _quat_conj(q: np.ndarray) -> np.ndarray:
        return np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float32)

    @staticmethod
    def _quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return np.array(
            [
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz,
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _quat_slerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
        a = HybridFusionEngine._normalize_quat(a)
        b = HybridFusionEngine._normalize_quat(b)

        dot = float(np.dot(a, b))
        if dot < 0.0:
            b = -b
            dot = -dot

        if dot > 0.9995:
            out = a + t * (b - a)
            return HybridFusionEngine._normalize_quat(out)

        theta_0 = float(np.arccos(np.clip(dot, -1.0, 1.0)))
        theta = theta_0 * t
        s0 = np.sin(theta_0 - theta) / np.sin(theta_0)
        s1 = np.sin(theta) / np.sin(theta_0)
        return s0 * a + s1 * b

    @staticmethod
    def _quat_from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
        half = angle * 0.5
        s = np.sin(half)
        return HybridFusionEngine._normalize_quat(np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(half)], dtype=np.float32))

    @staticmethod
    def _axis_angle_from_quat(q: np.ndarray) -> tuple[np.ndarray, float]:
        q = HybridFusionEngine._normalize_quat(q)
        w = float(np.clip(q[3], -1.0, 1.0))
        angle = 2.0 * np.arccos(w)
        s = np.sqrt(max(1.0 - w * w, 0.0))
        if s < 1e-6:
            return np.array([1.0, 0.0, 0.0], dtype=np.float32), 0.0
        return np.array([q[0] / s, q[1] / s, q[2] / s], dtype=np.float32), float(angle)
