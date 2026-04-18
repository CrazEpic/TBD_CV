from __future__ import annotations

import numpy as np

from .base import InstrumentModule


class ViolinModule(InstrumentModule):
    def __init__(self, profile: dict | None = None) -> None:
        profile = profile or {}

        self._string_scores = {"G": 0.0, "D": 0.0, "A": 0.0, "E": 0.0}
        self._left_x_ema = None
        self._prev_right_wrist_local = None
        self._prev_t = None

        self._string_centers = {
            "G": float(profile.get("string_centers", {}).get("G", 0.030)),
            "D": float(profile.get("string_centers", {}).get("D", 0.010)),
            "A": float(profile.get("string_centers", {}).get("A", -0.010)),
            "E": float(profile.get("string_centers", {}).get("E", -0.030)),
        }
        self._string_width = float(profile.get("string_width", 0.018))
        self._position_bins = [float(x) for x in profile.get("position_bins", [0.03, 0.08, 0.13, 0.18])]
        self._bow_pressure_center_y = float(profile.get("bow_pressure_center_y", -0.12))
        self._bow_pressure_half_width = float(profile.get("bow_pressure_half_width", 0.08))

    def name(self) -> str:
        return "violin"

    def estimate_pose(self, features: dict):
        pose = features.get("pose")
        left = features.get("left")
        right = features.get("right")

        if pose is None:
            return None

        joints = pose["joints"]
        left_shoulder = np.asarray(joints["left_shoulder"], dtype=np.float32)
        right_shoulder = np.asarray(joints["right_shoulder"], dtype=np.float32)
        nose = np.asarray(joints["nose"], dtype=np.float32)
        left_ear = np.asarray(joints["left_ear"], dtype=np.float32)
        right_ear = np.asarray(joints["right_ear"], dtype=np.float32)
        left_wrist = np.asarray(joints["left_wrist"], dtype=np.float32)
        left_elbow = np.asarray(joints["left_elbow"], dtype=np.float32)

        body_up = np.asarray(pose["torso"]["body_up"], dtype=np.float32)

        shoulder_line = self._normalize(right_shoulder - left_shoulder)
        head_center = (nose + left_ear + right_ear) / 3.0

        # Violin sits on the left shoulder and points forward-left.
        neck_axis = self._normalize((left_wrist - left_shoulder) + shoulder_line * 0.35)
        body_axis = self._normalize(np.cross(body_up, shoulder_line))
        if np.linalg.norm(body_axis) < 1e-8:
            body_axis = self._normalize(np.cross(neck_axis, body_up))

        # Use a consistent right-handed frame for drawing.
        up = self._normalize(np.cross(neck_axis, body_axis))

        center = (left_shoulder * 0.70 + left_elbow * 0.15 + left_wrist * 0.15).tolist()
        neck_end = (np.asarray(center, dtype=np.float32) + neck_axis * 0.22).tolist()
        body_end = (np.asarray(center, dtype=np.float32) - body_axis * 0.14).tolist()
        chin_anchor = (left_shoulder * 0.35 + head_center * 0.65).tolist()

        confidence = 0.30
        if left is not None:
            confidence += 0.25
        if right is not None:
            confidence += 0.10
        if np.linalg.norm(body_up) > 1e-6:
            confidence += 0.10
        if np.linalg.norm(left_wrist - left_shoulder) > 1e-6:
            confidence += 0.15
        if np.linalg.norm(nose - left_shoulder) > 1e-6:
            confidence += 0.10

        return {
            "type": self.name(),
            "center": center,
            "neck_end": neck_end,
            "body_end": body_end,
            "chin_anchor": chin_anchor,
            "axis": neck_axis.tolist(),
            "body_axis": body_axis.tolist(),
            "up": up.tolist(),
            "confidence": float(min(confidence, 1.0)),
        }

    def process(self, features: dict, context: dict | None = None) -> dict:
        context = context or {}
        left = features.get("left")
        right = features.get("right")
        instrument_pose = context.get("instrument_pose")
        frame_width = int(context.get("frame_width", 0))
        frame_height = int(context.get("frame_height", 0))
        intrinsics = context.get("intrinsics")
        timestamp = float(features.get("timestamp", 0.0))

        left_hand = {
            "string": "A",
            "finger_position": 0,
            "hand_shift": 0.0,
            "vibrato": 0.0,
            "finger_states": {k: 0.0 for k in ["thumb", "index", "middle", "ring", "pinky"]},
        }

        if (
            left is not None
            and instrument_pose is not None
            and intrinsics is not None
            and frame_width > 0
            and frame_height > 0
            and float(instrument_pose.get("confidence", 0.0)) > 0.05
        ):
            center = np.asarray(instrument_pose.get("position", [0.0, 0.0, 0.0]), dtype=np.float32)
            quat = np.asarray(instrument_pose.get("rotation", [0.0, 0.0, 0.0, 1.0]), dtype=np.float32)

            tips = left.get("tips", {})
            index_tip = tips.get("index")
            middle_tip = tips.get("middle")
            ring_tip = tips.get("ring")
            pinky_tip = tips.get("pinky")
            wrist_norm = left.get("hand_pose", {}).get("wrist")

            if index_tip is not None and wrist_norm is not None:
                index_local = self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(index_tip, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )
                wrist_local = self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(wrist_norm, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )

                middle_local = index_local if middle_tip is None else self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(middle_tip, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )
                ring_local = index_local if ring_tip is None else self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(ring_tip, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )
                pinky_local = index_local if pinky_tip is None else self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(pinky_tip, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )

                string_contact = self._estimate_string_from_local(index_local[2])
                finger_x = float(np.mean([index_local[0], middle_local[0], ring_local[0]]))
                if self._left_x_ema is None:
                    self._left_x_ema = finger_x
                self._left_x_ema = 0.7 * self._left_x_ema + 0.3 * finger_x
                finger_position = self._finger_position_from_x(self._left_x_ema)

                finger_states = {
                    "thumb": float(left["fingers"]["thumb"]["curled_score"]),
                    "index": float(np.clip(1.0 - abs(index_local[1]) / 0.05, 0.0, 1.0)),
                    "middle": float(np.clip(1.0 - abs(middle_local[1]) / 0.05, 0.0, 1.0)),
                    "ring": float(np.clip(1.0 - abs(ring_local[1]) / 0.05, 0.0, 1.0)),
                    "pinky": float(np.clip(1.0 - abs(pinky_local[1]) / 0.05, 0.0, 1.0)),
                }

                left_hand = {
                    "string": string_contact,
                    "finger_position": finger_position,
                    "hand_shift": float(np.clip((self._left_x_ema + 0.05) / 0.25, 0.0, 1.0)),
                    "vibrato": float(np.clip(left["motion"]["wrist_speed"] * 0.15, 0.0, 1.0)),
                    "finger_states": finger_states,
                    "wrist": wrist_local.tolist(),
                    "hand_forward": np.asarray(left["hand_pose"]["hand_forward"], dtype=np.float32).tolist(),
                }

        right_hand = {
            "bow_speed": 0.0,
            "bow_pressure": 0.0,
            "bow_position": 0.0,
            "bow_direction": "down",
            "bow_angle": 0.0,
        }

        if (
            right is not None
            and instrument_pose is not None
            and intrinsics is not None
            and frame_width > 0
            and frame_height > 0
            and float(instrument_pose.get("confidence", 0.0)) > 0.05
        ):
            center = np.asarray(instrument_pose.get("position", [0.0, 0.0, 0.0]), dtype=np.float32)
            quat = np.asarray(instrument_pose.get("rotation", [0.0, 0.0, 0.0, 1.0]), dtype=np.float32)
            right_wrist_norm = right.get("hand_pose", {}).get("wrist")
            right_index_norm = right.get("tips", {}).get("index")
            if right_wrist_norm is not None and right_index_norm is not None:
                right_wrist_local = self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(right_wrist_norm, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )
                right_index_local = self._world_to_instrument_local(
                    self._normalized_to_camera(np.asarray(right_index_norm, dtype=np.float32), frame_width, frame_height, intrinsics),
                    center,
                    quat,
                )

                bow_speed = 0.0
                bow_direction = right_hand["bow_direction"]
                if self._prev_right_wrist_local is not None and self._prev_t is not None:
                    dt = max(timestamp - self._prev_t, 1e-3)
                    bow_vel = (right_wrist_local - self._prev_right_wrist_local) / dt
                    bow_speed = float(np.clip(np.linalg.norm(bow_vel) * 0.15, 0.0, 1.0))
                    bow_direction = "up" if bow_vel[0] < 0.0 else "down"

                self._prev_right_wrist_local = right_wrist_local.copy()
                self._prev_t = timestamp

                bow_vec = right_index_local - right_wrist_local
                bow_angle = float(np.degrees(np.arctan2(bow_vec[1], bow_vec[0])))
                bow_position = float(np.clip((right_wrist_local[0] + 0.10) / 0.35, 0.0, 1.0))
                bow_pressure = float(
                    np.clip(
                        1.0 - abs(right_wrist_local[1] - self._bow_pressure_center_y) / self._bow_pressure_half_width,
                        0.0,
                        1.0,
                    )
                )

                right_hand = {
                    "bow_speed": bow_speed,
                    "bow_pressure": bow_pressure,
                    "bow_position": bow_position,
                    "bow_direction": bow_direction,
                    "bow_angle": bow_angle,
                    "wrist_velocity": np.asarray(right["motion"]["wrist_velocity"], dtype=np.float32).tolist(),
                }

        return {
            "type": self.name(),
            "left_hand": left_hand,
            "right_hand": right_hand,
        }

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v)
        if norm < 1e-8:
            return np.array([0.0, 0.0, 0.0], dtype=np.float32)
        return v / norm

    def _estimate_string_from_local(self, lateral_z: float) -> str:
        for name, cz in self._string_centers.items():
            score = float(np.exp(-abs(lateral_z - cz) / self._string_width))
            self._string_scores[name] = 0.7 * self._string_scores[name] + 0.3 * score
        return max(self._string_scores, key=self._string_scores.get)

    def _finger_position_from_x(self, local_x: float) -> int:
        b0, b1, b2, b3 = self._position_bins
        if local_x < b0:
            return 0
        if local_x < b1:
            return 1
        if local_x < b2:
            return 2
        if local_x < b3:
            return 3
        return 4

    @staticmethod
    def _normalized_to_camera(point: np.ndarray, width: int, height: int, intrinsics: dict) -> np.ndarray:
        u = float(point[0]) * width
        v = float(point[1]) * height
        z_norm = float(point[2]) if point.shape[0] > 2 else 0.0
        z = max(0.05, 0.80 + (-z_norm) * 0.65)
        x = (u - intrinsics["cx"]) * z / intrinsics["fx"]
        y = (v - intrinsics["cy"]) * z / intrinsics["fy"]
        return np.array([x, y, z], dtype=np.float32)

    @staticmethod
    def _world_to_instrument_local(world: np.ndarray, center: np.ndarray, quat_xyzw: np.ndarray) -> np.ndarray:
        q = ViolinModule._normalize_quat(quat_xyzw)
        q_conj = np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float32)
        v = world - center
        return ViolinModule._quat_rotate(q_conj, v)

    @staticmethod
    def _quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        x, y, z, w = q
        qv = np.array([v[0], v[1], v[2], 0.0], dtype=np.float32)
        qq = np.array([x, y, z, w], dtype=np.float32)
        qc = np.array([-x, -y, -z, w], dtype=np.float32)
        return ViolinModule._quat_mul(ViolinModule._quat_mul(qq, qv), qc)[:3]

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
    def _normalize_quat(q: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(q)
        if n < 1e-8:
            return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        return q / n
