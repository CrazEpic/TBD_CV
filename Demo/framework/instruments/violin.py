from __future__ import annotations

import numpy as np

from .base import InstrumentModule
from ..audio_engine import get_audio_engine


class ViolinModule(InstrumentModule):
    def __init__(self, profile: dict | None = None) -> None:
        profile = profile or {}

        self._string_scores = {"G": 0.0, "D": 0.0, "A": 0.0, "E": 0.0}
        self._left_x_ema = None
        self._prev_right_wrist_local = None
        self._prev_t = None
        self._arm_elevation_ema = None  # For temporal smoothing of arm elevation signal
        
        # Audio synthesis for note playback
        self._audio_engine = get_audio_engine()
        self._current_playing_note = None
        self._last_bow_speed = 0.0

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
        
        # Right arm elevation thresholds for string detection
        # Arm elevation goes from 0 (E string) to 1 (G string)
        self._arm_elevation_thresholds = {
            "E": float(profile.get("arm_elevation_E", 0.20)),   # Elbow low, arm down
            "A": float(profile.get("arm_elevation_A", 0.40)),   # Elbow medium
            "D": float(profile.get("arm_elevation_D", 0.60)),   # Elbow higher
            "G": float(profile.get("arm_elevation_G", 0.80)),   # Elbow high, arm lifted
        }
        
        # Finger detection thresholds
        self._finger_contact_threshold_lifted = 0.08      # > this = lifted
        self._finger_contact_threshold_touched = 0.05     # between 0.02-0.05 = touching
        self._finger_contact_threshold_pressed = 0.02     # < this = pressed
        self._finger_flexion_threshold_pressed = 0.25     # flexion score for pressing (lowered for easier detection)


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

                # NEW: Use right-arm-based detection instead of left hand Z-position
                pose = features.get("pose")
                string_contact = self._estimate_string_from_arm_elevation(pose)
                
                # Keep left hand analysis for finger position and states
                finger_x = float(np.mean([index_local[0], middle_local[0], ring_local[0]]))
                if self._left_x_ema is None:
                    self._left_x_ema = finger_x
                self._left_x_ema = 0.7 * self._left_x_ema + 0.3 * finger_x
                finger_position = self._finger_position_from_x(self._left_x_ema)

                # Enhanced finger detection using angle-based approach
                string_baseline_y = wrist_local[1]  # Use wrist as reference for string position
                
                # Use angle data from FeatureExtractor (pip_angle and dip_angle)
                # which directly measure joint bending
                fingers_data = left.get("fingers", {})
                
                # Detect contact state for each finger
                finger_contact_states = {}
                for finger_name in ["index", "middle", "ring", "pinky"]:
                    finger_info = fingers_data.get(finger_name, {})
                    pip_angle = float(finger_info.get("pip_angle_deg", 180.0))
                    dip_angle = float(finger_info.get("dip_angle_deg", 180.0))
                    
                    # Get fingertip position in local coordinates
                    if finger_name == "index":
                        finger_local = index_local
                    elif finger_name == "middle":
                        finger_local = middle_local
                    elif finger_name == "ring":
                        finger_local = ring_local
                    else:  # pinky
                        finger_local = pinky_local
                    
                    y_distance = abs(float(finger_local[1]) - float(string_baseline_y))
                    
                    # Detect state based on Y-distance AND joint angles
                    # When fully extended: pip_angle ~ 180°, dip_angle ~ 180°
                    # When pressed/curled: both angles significantly lower
                    
                    if y_distance > 0.08:
                        contact = 'lifted'  # Too far from string
                    elif y_distance < 0.02 and pip_angle < 120 and dip_angle < 120:
                        contact = 'pressed'  # Close to string AND both joints are bent
                    elif y_distance < 0.06 and (pip_angle < 150 or dip_angle < 150):
                        contact = 'touching'  # Near string AND some bending
                    else:
                        contact = 'lifted'  # Either too far or too extended
                    
                    finger_contact_states[finger_name] = contact
                
                # Detect which finger is actively fretting
                active_finger = self._detect_active_finger(finger_contact_states)
                
                # Convert to note
                note_name = self._finger_position_to_note(string_contact, active_finger)

                # Combine old and new finger state information
                finger_states = {
                    "thumb": float(left["fingers"]["thumb"]["curled_score"]),
                    "index": float(np.clip(1.0 - abs(index_local[1]) / 0.05, 0.0, 1.0)),
                    "middle": float(np.clip(1.0 - abs(middle_local[1]) / 0.05, 0.0, 1.0)),
                    "ring": float(np.clip(1.0 - abs(ring_local[1]) / 0.05, 0.0, 1.0)),
                    "pinky": float(np.clip(1.0 - abs(pinky_local[1]) / 0.05, 0.0, 1.0)),
                    # New: categorical contact states
                    "contact_states": finger_contact_states,
                    # New: active finger index
                    "active_finger": int(active_finger),
                }

                left_hand = {
                    "string": string_contact,
                    "finger_position": finger_position,
                    "hand_shift": float(np.clip((self._left_x_ema + 0.05) / 0.25, 0.0, 1.0)),
                    "vibrato": float(np.clip(left["motion"]["wrist_speed"] * 0.15, 0.0, 1.0)),
                    "finger_states": finger_states,
                    "active_finger": int(active_finger),  # New: which finger is pressing
                    "note": note_name,  # New: the note being played
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
                
                # Audio playback: Play note when bow is moving with a finger pressed
                self._handle_audio_playback(left_hand, bow_speed)

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

    def _estimate_string_from_arm_elevation(self, pose: dict) -> str:
        """
        Detect string based on right arm elevation (bow arm).
        
        Combines two features:
        1. Elbow height relative to shoulder (low → high: E → G)
        2. Shoulder abduction angle (arm pointing down → lifted: E → G)
        
        Returns: String name "E", "A", "D", or "G"
        """
        if pose is None:
            return "A"  # Default if no pose
        
        joints = pose.get("joints", {})
        right_shoulder = np.asarray(joints.get("right_shoulder", [0, 0, 0]), dtype=np.float32)
        right_elbow = np.asarray(joints.get("right_elbow", [0, 0, 0]), dtype=np.float32)
        right_wrist = np.asarray(joints.get("right_wrist", [0, 0, 0]), dtype=np.float32)
        body_up = np.asarray(pose.get("torso", {}).get("body_up", [0, 1, 0]), dtype=np.float32)
        
        # Normalize body_up if needed
        if np.linalg.norm(body_up) < 1e-8:
            body_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        else:
            body_up = body_up / np.linalg.norm(body_up)
        
        # Feature 1: Elbow height relative to shoulder
        # Positive body_up component means higher; negative means lower
        elbow_displacement = right_elbow - right_shoulder
        elbow_height = np.dot(elbow_displacement, body_up)  # Project onto vertical axis
        
        # # Normalize height to 0-1 range
        # # Assume shoulder to elbow distance ~ 0.3, so height ranges -0.3 to +0.3
        # height_normalized = np.clip((elbow_height + 0.15) / 0.30, 0.0, 1.0)
        # --- Normalize by actual upper arm length ---
        upper_arm_length = np.linalg.norm(right_elbow - right_shoulder)

        if upper_arm_length < 1e-6:
            height_normalized = 0.5  # fallback
        else:
            h_norm = elbow_height / upper_arm_length  # now roughly [-1, 1]

            # --- Asymmetric bounds (tune these) ---
            lower_bound = -0.8   # E string extreme
            upper_bound = 0.3    # G string extreme

            # Clamp to realistic playing range
            h_clamped = np.clip(h_norm, lower_bound, upper_bound)

            # Rescale to [0, 1]
            height_normalized = (h_clamped - lower_bound) / (upper_bound - lower_bound)
        
        # Feature 2: Shoulder abduction angle
        # Calculate upper arm vector (shoulder → elbow)
        upper_arm = self._normalize(right_elbow - right_shoulder)
        
        # Calculate horizontal plane (perpendicular to body_up)
        # Angle from vertical (body_up): 0° = arm pointing up/down (vertical), 90° = arm horizontal
        # Use absolute value of dot product to get angle magnitude
        dot_product = np.dot(upper_arm, body_up)
        angle_from_vertical = np.arccos(np.clip(abs(dot_product), 0.0, 1.0))
        angle_normalized = np.clip(angle_from_vertical / (np.pi / 2.0), 0.0, 1.0)  # 0-1
        
        # Combine features: 60% height + 40% abduction angle
        # This gives more weight to how high the elbow is
        arm_elevation = 0.7 * height_normalized + 0.3 * angle_normalized
        
        # Apply EMA smoothing for temporal stability
        if self._arm_elevation_ema is None:
            self._arm_elevation_ema = arm_elevation
        self._arm_elevation_ema = 0.6 * self._arm_elevation_ema + 0.4 * arm_elevation
        
        # Map arm elevation to string using thresholds
        # arm_elevation goes from 0 (E string) to 1 (G string)
        if self._arm_elevation_ema < self._arm_elevation_thresholds["E"]:
            return "E"
        elif self._arm_elevation_ema < self._arm_elevation_thresholds["A"]:
            # Interpolate between E and A
            if self._arm_elevation_ema < (self._arm_elevation_thresholds["E"] + self._arm_elevation_thresholds["A"]) / 2:
                return "E"
            else:
                return "A"
        elif self._arm_elevation_ema < self._arm_elevation_thresholds["D"]:
            # Interpolate between A and D
            if self._arm_elevation_ema < (self._arm_elevation_thresholds["A"] + self._arm_elevation_thresholds["D"]) / 2:
                return "A"
            else:
                return "D"
        elif self._arm_elevation_ema < self._arm_elevation_thresholds["G"]:
            # Interpolate between D and G
            if self._arm_elevation_ema < (self._arm_elevation_thresholds["D"] + self._arm_elevation_thresholds["G"]) / 2:
                return "D"
            else:
                return "G"
        else:
            return "G"

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

    def _extract_finger_joints(self, finger_tip: tuple | list | None, finger_pip: tuple | list | None, finger_mcp: tuple | list | None) -> dict | None:
        """
        Extract finger position and flexion information.
        
        Args:
            finger_tip: Fingertip position (3D normalized coordinates)
            finger_pip: Proximal interphalangeal joint (middle knuckle)
            finger_mcp: Metacarpophalangeal joint (base knuckle)
        
        Returns:
            Dict with 'tip', 'flexion', 'length' or None if data unavailable
        """
        if finger_tip is None or finger_pip is None or finger_mcp is None:
            return None
        
        try:
            tip = np.asarray(finger_tip, dtype=np.float32)
            pip = np.asarray(finger_pip, dtype=np.float32)
            mcp = np.asarray(finger_mcp, dtype=np.float32)
            
            # Distance from MCP to tip (fully extended)
            full_length = np.linalg.norm(tip - mcp)
            
            # Distance from MCP to PIP
            upper_length = np.linalg.norm(pip - mcp)
            
            # Flexion score (0 = fully extended, 1 = fully curled)
            if upper_length > 1e-6:
                flexion = np.clip(1.0 - (full_length / (upper_length * 2.0)), 0.0, 1.0)
            else:
                flexion = 0.0
            
            return {
                'tip': tip,
                'flexion': float(flexion),
                'length': float(full_length)
            }
        except Exception:
            return None

    def _detect_finger_contact(self, finger_data: dict | None, string_baseline_y: float, sensitivity: float = 0.02) -> str:
        """
        Detect if finger is touching the string.
        
        Args:
            finger_data: Finger joint information from _extract_finger_joints()
            string_baseline_y: Y-position where string runs
            sensitivity: Distance threshold for "pressed" state
        
        Returns:
            'lifted', 'touching', or 'pressed'
        """
        if finger_data is None:
            return 'lifted'
        
        try:
            y_distance = abs(float(finger_data['tip'][1]) - float(string_baseline_y))
            flexion = float(finger_data['flexion'])
            
            if y_distance > self._finger_contact_threshold_lifted:
                return 'lifted'
            
            if y_distance < sensitivity and flexion > self._finger_flexion_threshold_pressed:
                return 'pressed'
            
            if y_distance < self._finger_contact_threshold_touched:
                return 'touching'
            
            return 'lifted'
        except Exception:
            return 'lifted'

    def _detect_active_finger(self, finger_contact_states: dict) -> int:
        """Determine which finger is actively fretting (pressed down)."""
        fingers = ['index', 'middle', 'ring', 'pinky']
        
        for i, finger in enumerate(fingers, 1):
            if finger_contact_states.get(finger) == 'pressed':
                return i
        
        for i, finger in enumerate(fingers, 1):
            if finger_contact_states.get(finger) == 'touching':
                return i
        
        return 0

    def _finger_position_to_note(self, current_string: str, active_finger: int) -> str:
        """Map current string + active finger to musical note."""
        string_to_note = {
            "G": 7,
            "D": 2,
            "A": 9,
            "E": 4,
        }
        
        finger_to_semitone = {
            0: 0,
            1: 1,
            2: 2,
            3: 3,
            4: 4,
        }
        
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
        
        base_note = string_to_note.get(current_string, 4)
        semitone_offset = finger_to_semitone.get(active_finger, 0)
        final_note_index = (base_note + semitone_offset) % 12
        
        return note_names[final_note_index]
    
    def _handle_audio_playback(self, left_hand: dict, bow_speed: float):
        """
        Play audio when bow is moving and a note is selected.
        
        Conditions for playback:
        1. Bow speed > 0.5 (bow is moving fast enough)
        2. Active finger > 0 (a finger is pressed, not open string)
        3. Note is different from previous note (avoid re-triggering same note)
        """
        if self._audio_engine is None:
            return
        
        note = left_hand.get("note", "")
        active_finger = left_hand.get("active_finger", 0)
        finger_states = left_hand.get("finger_states", {})
        contact_states = finger_states.get("contact_states", {})
        
        # Check if any finger is pressed (not just touching)
        has_pressed_finger = any(
            state == "pressed" for state in contact_states.values()
        )
        
        # Only play if bow is moving significantly and finger is pressed
        is_bow_moving = bow_speed > 0.5
        should_play = is_bow_moving and has_pressed_finger and note
        
        # Check if note changed (to avoid retriggering the same note rapidly)
        note_changed = note != self._current_playing_note
        
        if should_play and note_changed:
            # Start playing the new note
            try:
                self._audio_engine.play_continuous(
                    note_name=note,
                    bow_speed=min(1.0, bow_speed * 1.5),  # Scale bow speed for volume
                    max_duration=2.0  # Max 2 seconds, will be interrupted by next note
                )
                self._current_playing_note = note
            except Exception as e:
                # Silently fail if audio engine has issues
                pass
        
        elif not should_play and self._current_playing_note is not None:
            # Stop playing if conditions are no longer met
            self._audio_engine.stop()
            self._current_playing_note = None
        
        self._last_bow_speed = bow_speed
