from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class PoseLandmark(IntEnum):
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


class HandLandmark(IntEnum):
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_FINGER_MCP = 5
    INDEX_FINGER_PIP = 6
    INDEX_FINGER_DIP = 7
    INDEX_FINGER_TIP = 8
    MIDDLE_FINGER_MCP = 9
    MIDDLE_FINGER_PIP = 10
    MIDDLE_FINGER_DIP = 11
    MIDDLE_FINGER_TIP = 12
    RING_FINGER_MCP = 13
    RING_FINGER_PIP = 14
    RING_FINGER_DIP = 15
    RING_FINGER_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


class LandmarkPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    z: float
    visibility: Optional[float] = None


class HolisticState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: float
    pose: Optional[list[LandmarkPoint]] = None
    left_hand: Optional[list[LandmarkPoint]] = None
    right_hand: Optional[list[LandmarkPoint]] = None
    face: Optional[list[LandmarkPoint]] = None
    confidences: Dict[str, float] = Field(default_factory=dict)

    @classmethod
    def pose_landmark_index(cls, landmark: PoseLandmark) -> int:
        return int(landmark)

    @classmethod
    def hand_landmark_index(cls, landmark: HandLandmark) -> int:
        return int(landmark)

    def get_pose_landmark(self, landmark: PoseLandmark) -> Optional[LandmarkPoint]:
        return self._get_landmark(self.pose, self.pose_landmark_index(landmark))

    def get_left_hand_landmark(self, landmark: HandLandmark) -> Optional[LandmarkPoint]:
        return self._get_landmark(self.left_hand, self.hand_landmark_index(landmark))

    def get_right_hand_landmark(self, landmark: HandLandmark) -> Optional[LandmarkPoint]:
        return self._get_landmark(self.right_hand, self.hand_landmark_index(landmark))

    @classmethod
    def from_mediapipe_results(cls, results: Any, timestamp: float) -> "HolisticState":
        return cls(
            timestamp=timestamp,
            pose=cls._convert_landmarks(results.pose_landmarks, include_visibility=True),
            left_hand=cls._convert_landmarks(results.left_hand_landmarks),
            right_hand=cls._convert_landmarks(results.right_hand_landmarks),
            face=cls._convert_landmarks(results.face_landmarks),
            confidences={
                "pose": cls._confidence(results.pose_landmarks),
                "left_hand": cls._confidence(results.left_hand_landmarks),
                "right_hand": cls._confidence(results.right_hand_landmarks),
                "face": cls._confidence(results.face_landmarks),
            },
        )

    @staticmethod
    def _convert_landmarks(landmarks: Any, include_visibility: bool = False) -> Optional[list[LandmarkPoint]]:
        if not landmarks:
            return None

        points: list[LandmarkPoint] = []
        for landmark in landmarks.landmark:
            point_data = {
                "x": float(landmark.x),
                "y": float(landmark.y),
                "z": float(landmark.z),
            }
            if include_visibility:
                point_data["visibility"] = float(getattr(landmark, "visibility", 0.0))
            points.append(LandmarkPoint(**point_data))
        return points

    @staticmethod
    def _confidence(landmarks: Any) -> float:
        return 1.0 if landmarks else 0.0

    @staticmethod
    def _get_landmark(landmarks: Optional[list[LandmarkPoint]], index: int) -> Optional[LandmarkPoint]:
        if landmarks is None or index >= len(landmarks):
            return None
        return landmarks[index]
