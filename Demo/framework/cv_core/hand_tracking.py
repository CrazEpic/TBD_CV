from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import cv2
from mediapipe.python.solutions import holistic


LandmarkList = List[List[float]]


@dataclass
class HolisticState:
    """State from MediaPipe Holistic: pose + left/right hands."""
    timestamp: float
    pose: Optional[LandmarkList]  # 33 points [x, y, z, visibility]
    left_hand: Optional[LandmarkList]  # 21 points [x, y, z]
    right_hand: Optional[LandmarkList]  # 21 points [x, y, z]
    face: Optional[LandmarkList]  # 468 points [x, y, z]
    confidences: dict


class MediaPipeHolisticTracker:
    """Tracks pose and hands using MediaPipe Holistic (matches demo_alt.py)."""

    def __init__(
        self,
        camera_index: int = 0,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._cap = cv2.VideoCapture(camera_index)
        self._holistic = holistic.Holistic(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def read(self) -> Tuple[bool, Optional[Any]]:
        return self._cap.read()

    def is_opened(self) -> bool:
        return bool(self._cap.isOpened())

    def process(self, frame_bgr: Any) -> HolisticState:
        """Process frame and extract holistic landmarks."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._holistic.process(rgb)

        # Extract pose (33 points with visibility)
        pose: Optional[LandmarkList] = None
        if results.pose_landmarks:
            pose = [[lm.x, lm.y, lm.z, lm.visibility] for lm in results.pose_landmarks.landmark]

        # Extract left hand (21 points, no visibility)
        left_hand: Optional[LandmarkList] = None
        if results.left_hand_landmarks:
            left_hand = [[lm.x, lm.y, lm.z] for lm in results.left_hand_landmarks.landmark]

        # Extract right hand (21 points, no visibility)
        right_hand: Optional[LandmarkList] = None
        if results.right_hand_landmarks:
            right_hand = [[lm.x, lm.y, lm.z] for lm in results.right_hand_landmarks.landmark]

        # Extract face mesh landmarks (used for flute alignment).
        face: Optional[LandmarkList] = None
        if results.face_landmarks:
            face = [[lm.x, lm.y, lm.z] for lm in results.face_landmarks.landmark]

        pose_conf = float(sum(p[3] for p in pose) / len(pose)) if pose is not None and len(pose) > 0 else 0.0
        left_conf = 1.0 if left_hand is not None else 0.0
        right_conf = 1.0 if right_hand is not None else 0.0
        face_conf = 1.0 if face is not None else 0.0

        return HolisticState(
            timestamp=time.time(),
            pose=pose,
            left_hand=left_hand,
            right_hand=right_hand,
            face=face,
            confidences={
                "pose": pose_conf,
                "left_hand": left_conf,
                "right_hand": right_conf,
                "face": face_conf,
            },
        )

    def draw_debug(self, frame_bgr: Any, state: HolisticState) -> Any:
        """Draw landmarks on frame for visualization."""
        # This would require re-extracting results, so caller should handle drawing.
        # For now, return frame unchanged (caller uses MediaPipe drawing if needed).
        return frame_bgr

    def close(self) -> None:
        self._holistic.close()
        self._cap.release()
