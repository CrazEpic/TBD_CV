from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
from mediapipe.framework.formats import landmark_pb2

from core.models.mediapipe_holistic_state import HolisticState
from core.models.mediapipe_violin_state import ViolinState, ViolinStateEstimator
from core.models.violin import ViolinProfile, load_violin_profile


def _to_landmark_list(points, include_visibility: bool = False):
    landmarks = landmark_pb2.NormalizedLandmarkList()
    for point in points or []:
        landmark = landmarks.landmark.add()
        landmark.x = point.x
        landmark.y = point.y
        landmark.z = point.z
        if include_visibility and point.visibility is not None:
            landmark.visibility = point.visibility
    return landmarks


def load_violin_profile_safe(path: str | Path) -> ViolinProfile:
    try:
        return load_violin_profile(path)
    except Exception:
        return ViolinProfile()


def draw_scene(frame, state: HolisticState, violin_profile: Optional[ViolinProfile] = None) -> None:
    mp_drawing = mp.solutions.drawing_utils
    mp_holistic = mp.solutions.holistic

    if state.pose:
        mp_drawing.draw_landmarks(
            frame,
            _to_landmark_list(state.pose, include_visibility=True),
            mp_holistic.POSE_CONNECTIONS,
        )

    if state.left_hand:
        mp_drawing.draw_landmarks(
            frame,
            _to_landmark_list(state.left_hand),
            mp_holistic.HAND_CONNECTIONS,
        )

    if state.right_hand:
        mp_drawing.draw_landmarks(
            frame,
            _to_landmark_list(state.right_hand),
            mp_holistic.HAND_CONNECTIONS,
        )

    profile = violin_profile or ViolinProfile()
    violin_state = ViolinStateEstimator().estimate(state, profile)
    if violin_state is not None:
        draw_violin_from_state(frame, profile, violin_state)


def draw_violin_from_state(frame, violin_profile: ViolinProfile, violin_state: ViolinState) -> None:
    h, w = frame.shape[:2]

    def project_to_px(point_2d: tuple[float, float]) -> tuple[int, int]:
        return int(point_2d[0] * w), int(point_2d[1] * h)

    origin_local = violin_profile.pnp_keypoints.chin_anchor
    geom = violin_profile.geometry

    body_poly = [
        project_to_px(violin_state.transform_local_xz(point, origin_local))
        for point in geom.body_outline
    ]
    if len(body_poly) >= 3:
        for i in range(len(body_poly)):
            p1 = body_poly[i]
            p2 = body_poly[(i + 1) % len(body_poly)]
            cv2.line(frame, p1, p2, (100, 200, 255), 2)

    string_colors = {
        "G": (0, 255, 255),
        "D": (255, 255, 0),
        "A": (255, 0, 255),
        "E": (0, 255, 0),
    }

    for name in ["G", "D", "A", "E"]:
        segment = getattr(geom.strings, name)
        p1 = project_to_px(violin_state.transform_local_xz(segment[0], origin_local))
        p2 = project_to_px(violin_state.transform_local_xz(segment[1], origin_local))
        color = string_colors[name]
        cv2.line(frame, p1, p2, color, 2)
        mx = int((p1[0] + p2[0]) * 0.5)
        my = int((p1[1] + p2[1]) * 0.5)
        cv2.putText(frame, name, (mx + 4, my - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)

    anchor_px = project_to_px((violin_state.anchor[0], violin_state.anchor[1]))
    cv2.circle(frame, anchor_px, 8, (0, 200, 255), 2)
    cv2.putText(frame, "chin_anchor", (anchor_px[0] + 10, anchor_px[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
