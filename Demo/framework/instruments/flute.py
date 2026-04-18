from __future__ import annotations

import numpy as np

from .base import InstrumentModule


class FluteModule(InstrumentModule):
    def __init__(self, profile: dict | None = None) -> None:
        profile = profile or {}

        self._pressed_state: dict[str, bool] = {}
        self._on_counts: dict[str, int] = {}
        self._off_counts: dict[str, int] = {}

        centers = profile.get("key_centers", {})

        # Instrument-local key locations (x: flute axis, y: up, z: lateral).
        self._key_centers = {
            "hole1": np.array(centers.get("hole1", [-0.030, 0.000, 0.015]), dtype=np.float32),
            "hole2": np.array(centers.get("hole2", [0.015, 0.000, 0.010]), dtype=np.float32),
            "hole3": np.array(centers.get("hole3", [0.060, 0.000, 0.008]), dtype=np.float32),
            "hole4": np.array(centers.get("hole4", [0.125, 0.000, -0.004]), dtype=np.float32),
            "hole5": np.array(centers.get("hole5", [0.175, 0.000, -0.007]), dtype=np.float32),
            "hole6": np.array(centers.get("hole6", [0.235, 0.000, -0.010]), dtype=np.float32),
        }
        self._key_radius = float(profile.get("key_radius", 0.038))
        self._on_threshold = float(profile.get("key_on_threshold", 0.62))
        self._off_threshold = float(profile.get("key_off_threshold", 0.42))
        self._hold_frames = int(profile.get("key_hold_frames", 2))

    def name(self) -> str:
        return "flute"

    def estimate_pose(self, features: dict):
        pose = features.get("pose")
        left = features.get("left")
        right = features.get("right")

        if pose is None:
            return None

        joints = pose["joints"]
        left_wrist = np.asarray(joints["left_wrist"], dtype=np.float32)
        right_wrist = np.asarray(joints["right_wrist"], dtype=np.float32)
        left_shoulder = np.asarray(joints["left_shoulder"], dtype=np.float32)
        right_shoulder = np.asarray(joints["right_shoulder"], dtype=np.float32)
        nose = np.asarray(joints["nose"], dtype=np.float32)
        mouth_left = np.asarray(joints["mouth_left"], dtype=np.float32)
        mouth_right = np.asarray(joints["mouth_right"], dtype=np.float32)

        mouth_center = (mouth_left + mouth_right) * 0.5
        shoulder_center = np.asarray(pose["torso"]["shoulder_center"], dtype=np.float32)
        shoulder_line = self._normalize(right_shoulder - left_shoulder)

        # Flute is held horizontally to the right, slightly downward.
        flute_axis = self._normalize((right_wrist - left_wrist) + shoulder_line * 0.18)
        if np.linalg.norm(flute_axis) < 1e-8:
            flute_axis = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        slight_down = np.array([0.0, 0.15, 0.0], dtype=np.float32)
        flute_axis = self._normalize(flute_axis + slight_down)
        up = self._normalize(np.cross(np.array([0.0, 0.0, 1.0], dtype=np.float32), flute_axis))
        if np.linalg.norm(up) < 1e-8:
            up = np.array([0.0, -1.0, 0.0], dtype=np.float32)

        center = (mouth_center * 0.40 + left_wrist * 0.28 + right_wrist * 0.32).tolist()
        embouchure_point = (mouth_center + flute_axis * 0.05).tolist()
        right_end = (np.asarray(center, dtype=np.float32) + flute_axis * 0.35).tolist()
        left_end = (np.asarray(center, dtype=np.float32) - flute_axis * 0.12).tolist()

        distance_to_mouth = float(np.linalg.norm((left_wrist + right_wrist) * 0.5 - mouth_center))
        shoulder_width = float(np.linalg.norm(right_shoulder - left_shoulder))
        proximity = 0.0
        if shoulder_width > 1e-6:
            proximity = max(0.0, 1.0 - distance_to_mouth / (shoulder_width * 1.4))

        head_rotation = float(np.clip((nose[0] - shoulder_center[0]) * 2.0, -1.0, 1.0))

        confidence = 0.30
        if left is not None:
            confidence += 0.20
        if right is not None:
            confidence += 0.20
        confidence += 0.30 * proximity

        return {
            "type": self.name(),
            "center": center,
            "left_end": left_end,
            "right_end": right_end,
            "embouchure_point": embouchure_point,
            "axis": flute_axis.tolist(),
            "up": up.tolist(),
            "head_rotation": head_rotation,
            "confidence": float(min(confidence, 1.0)),
        }

    def process(self, features: dict, context: dict | None = None) -> dict:
        context = context or {}
        pose = features.get("pose")
        left = features.get("left")
        right = features.get("right")

        instrument_pose = context.get("instrument_pose")
        frame_width = int(context.get("frame_width", 0))
        frame_height = int(context.get("frame_height", 0))
        intrinsics = context.get("intrinsics")

        fingering = {
            "thumb": False,
            "index_L": False,
            "middle_L": False,
            "ring_L": False,
            "index_R": False,
            "middle_R": False,
            "ring_R": False,
            "pinky_R": False,
        }
        holes_covered = []

        embouchure = {
            "air_speed": 0.0,
            "air_angle": 0.0,
            "air_pressure": 0.0,
            "lip_aperture_size": 0.0,
            "lip_opening_width": 0.0,
            "lip_coverage": 0.0,
            "jet_direction_angle": 0.0,
            "tone": 0.0,
            "register": 1,
        }

        if (
            instrument_pose is not None
            and intrinsics is not None
            and frame_width > 0
            and frame_height > 0
            and float(instrument_pose.get("confidence", 0.0)) > 0.05
            and left is not None
            and right is not None
        ):
            center = np.asarray(instrument_pose.get("position", [0.0, 0.0, 0.0]), dtype=np.float32)
            quat = np.asarray(instrument_pose.get("rotation", [0.0, 0.0, 0.0, 1.0]), dtype=np.float32)

            left_tips = left.get("tips", {})
            right_tips = right.get("tips", {})

            finger_map = {
                "hole1": left_tips.get("thumb"),
                "hole2": left_tips.get("index"),
                "hole3": left_tips.get("middle"),
                "hole4": right_tips.get("index"),
                "hole5": right_tips.get("middle"),
                "hole6": right_tips.get("ring"),
            }

            hole_pressed: dict[str, bool] = {}
            for hole, tip in finger_map.items():
                if tip is None:
                    hole_pressed[hole] = self._pressed_state.get(hole, False)
                    continue

                tip_cam = self._normalized_to_camera(
                    point=np.asarray(tip, dtype=np.float32),
                    width=frame_width,
                    height=frame_height,
                    intrinsics=intrinsics,
                )
                tip_local = self._world_to_instrument_local(tip_cam, center, quat)
                key_center = self._key_centers[hole]
                dist = float(np.linalg.norm(tip_local - key_center))
                score = float(np.clip(1.0 - dist / self._key_radius, 0.0, 1.0))
                hole_pressed[hole] = self._update_binary_state(
                    hole,
                    score,
                    on_thr=self._on_threshold,
                    off_thr=self._off_threshold,
                    hold_frames=self._hold_frames,
                )

            fingering["thumb"] = hole_pressed["hole1"]
            fingering["index_L"] = hole_pressed["hole2"]
            fingering["middle_L"] = hole_pressed["hole3"]
            fingering["ring_L"] = hole_pressed["hole4"]
            fingering["index_R"] = hole_pressed["hole4"]
            fingering["middle_R"] = hole_pressed["hole5"]
            fingering["ring_R"] = hole_pressed["hole6"]
            fingering["pinky_R"] = hole_pressed["hole6"]

            for hole_name, pressed in hole_pressed.items():
                if pressed:
                    holes_covered.append(hole_name)

        if pose is not None:
            joints = pose["joints"]
            mouth_left = np.asarray(joints["mouth_left"], dtype=np.float32)
            mouth_right = np.asarray(joints["mouth_right"], dtype=np.float32)
            nose = np.asarray(joints["nose"], dtype=np.float32)
            left_shoulder = np.asarray(joints["left_shoulder"], dtype=np.float32)
            right_shoulder = np.asarray(joints["right_shoulder"], dtype=np.float32)
            left_wrist = np.asarray(joints["left_wrist"], dtype=np.float32)
            right_wrist = np.asarray(joints["right_wrist"], dtype=np.float32)

            mouth_center = (mouth_left + mouth_right) * 0.5
            shoulder_width = float(np.linalg.norm(right_shoulder - left_shoulder))
            wrist_span = float(np.linalg.norm(right_wrist - left_wrist))
            flute_span = max(wrist_span, shoulder_width * 0.6)

            air_speed = 0.0
            air_pressure = 0.0
            lip_aperture_size = float(np.clip(1.0 - abs(nose[1] - mouth_center[1]) * 4.0, 0.0, 1.0))
            lip_opening_width = float(np.clip(abs(mouth_right[0] - mouth_left[0]) * 6.0, 0.0, 1.0))
            lip_coverage = float(np.clip(1.0 - abs(left_wrist[1] - mouth_center[1]) * 3.0, 0.0, 1.0))
            jet_direction_angle = float(np.degrees(np.arctan2(mouth_center[1] - nose[1], mouth_center[0] - nose[0])))

            if left is not None:
                air_speed += float(left["motion"]["wrist_speed"] * 0.35)
                air_pressure += float(left["fingers"]["thumb"]["curled_score"] * 0.15)
            if right is not None:
                air_speed += float(right["motion"]["wrist_speed"] * 0.25)
                air_pressure += float(right["fingers"]["index"]["curled_score"] * 0.10)

            air_speed = float(np.clip(air_speed, 0.0, 1.0))
            air_pressure = float(np.clip(air_pressure, 0.0, 1.0))
            register = 1 if air_speed < 0.33 or lip_aperture_size > 0.65 else (2 if air_speed < 0.66 else 3)
            tone = float(np.clip(0.45 * air_speed + 0.35 * air_pressure + 0.20 * (1.0 - lip_aperture_size), 0.0, 1.0))

            embouchure = {
                "air_speed": air_speed,
                "air_angle": jet_direction_angle,
                "air_pressure": air_pressure,
                "lip_aperture_size": lip_aperture_size,
                "lip_opening_width": lip_opening_width,
                "lip_coverage": lip_coverage,
                "jet_direction_angle": jet_direction_angle,
                "tone": tone,
                "register": register,
                "flute_span": float(flute_span),
            }

        return {
            "type": self.name(),
            "fingering": fingering,
            "holes_covered": holes_covered,
            "embouchure": embouchure,
        }

    def _update_binary_state(
        self,
        key: str,
        score: float,
        on_thr: float,
        off_thr: float,
        hold_frames: int,
    ) -> bool:
        state = self._pressed_state.get(key, False)

        if not state:
            if score >= on_thr:
                self._on_counts[key] = self._on_counts.get(key, 0) + 1
            else:
                self._on_counts[key] = 0
            self._off_counts[key] = 0
            if self._on_counts[key] >= hold_frames:
                self._pressed_state[key] = True
        else:
            if score <= off_thr:
                self._off_counts[key] = self._off_counts.get(key, 0) + 1
            else:
                self._off_counts[key] = 0
            self._on_counts[key] = 0
            if self._off_counts[key] >= hold_frames:
                self._pressed_state[key] = False

        return self._pressed_state.get(key, False)

    @staticmethod
    def _normalized_to_camera(point: np.ndarray, width: int, height: int, intrinsics: dict) -> np.ndarray:
        u = float(point[0]) * width
        v = float(point[1]) * height
        z_norm = float(point[2]) if point.shape[0] > 2 else 0.0
        z = max(0.05, 0.72 + (-z_norm) * 0.55)
        x = (u - intrinsics["cx"]) * z / intrinsics["fx"]
        y = (v - intrinsics["cy"]) * z / intrinsics["fy"]
        return np.array([x, y, z], dtype=np.float32)

    @staticmethod
    def _world_to_instrument_local(world: np.ndarray, center: np.ndarray, quat_xyzw: np.ndarray) -> np.ndarray:
        q = FluteModule._normalize_quat(quat_xyzw)
        q_conj = np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float32)
        v = world - center
        return FluteModule._quat_rotate(q_conj, v)

    @staticmethod
    def _quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        x, y, z, w = q
        qv = np.array([v[0], v[1], v[2], 0.0], dtype=np.float32)
        qq = np.array([x, y, z, w], dtype=np.float32)
        qc = np.array([-x, -y, -z, w], dtype=np.float32)
        return FluteModule._quat_mul(FluteModule._quat_mul(qq, qv), qc)[:3]

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

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v)
        if norm < 1e-8:
            return np.array([0.0, 0.0, 0.0], dtype=np.float32)
        return v / norm
