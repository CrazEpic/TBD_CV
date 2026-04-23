from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
from mediapipe.framework.formats import landmark_pb2

from core.models.mediapipe_holistic_state import HolisticState, PoseLandmark
from core.models.mediapipe_violin_state import ViolinState, ViolinStateEstimator
from core.models.violin import ViolinProfile, load_violin_profile


RATIO_PER_HALF_STEP = 0.943874312682  # pow(0.5, 1.0/12.0)
DEFAULT_HALF_STEP_COUNT = 8
USE_FIXED_STRING_LENGTH = True
FIXED_STRING_LENGTH_METERS = 0.328
FINGERING_POINT_RADIUS_PX = 3
FINGERING_POINT_COLOR_BGR = (0, 0, 255)
DRAW_ANCHOR_DEBUG = True


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


def _distance_from_fingerboard_end(half_step: int, string_length: float) -> float:
    # D(x) = L - L * (2^(-1/12))^x
    return string_length - (string_length * pow(RATIO_PER_HALF_STEP, half_step))


def _compute_fingering_points(
    string_segment: tuple[tuple[float, float, float], tuple[float, float, float]],
    half_step_count: int,
    use_fixed_string_length: bool,
    fixed_string_length: float,
) -> list[tuple[float, float, float]]:
    if half_step_count <= 0:
        return []

    bridge_side, fingerboard_end = string_segment
    direction = (
        bridge_side[0] - fingerboard_end[0],
        bridge_side[1] - fingerboard_end[1],
        bridge_side[2] - fingerboard_end[2],
    )
    measured_length = math.sqrt(
        direction[0] * direction[0] + direction[1] * direction[1] + direction[2] * direction[2]
    )
    if measured_length <= 1e-6:
        return []

    direction = (
        direction[0] / measured_length,
        direction[1] / measured_length,
        direction[2] / measured_length,
    )
    string_length = fixed_string_length if use_fixed_string_length else measured_length

    points: list[tuple[float, float, float]] = []
    for half_step in range(half_step_count):
        distance = _distance_from_fingerboard_end(half_step, string_length)
        points.append(
            (
                fingerboard_end[0] + direction[0] * distance,
                fingerboard_end[1] + direction[1] * distance,
                fingerboard_end[2] + direction[2] * distance,
            )
        )
    return points


def _draw_anchor_debug_markers(frame, state: HolisticState) -> None:
    h, w = frame.shape[:2]

    def to_px(x: float, y: float) -> tuple[int, int]:
        return int(x * w), int(y * h)

    def draw_pose_point(landmark, label: str, color: tuple[int, int, int]) -> None:
        if landmark is None:
            return
        p = to_px(landmark.x, landmark.y)
        cv2.circle(frame, p, 5, color, -1)
        cv2.putText(frame, label, (p[0] + 7, p[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)

    shoulder_l = state.get_pose_landmark(PoseLandmark.LEFT_SHOULDER)
    shoulder_r = state.get_pose_landmark(PoseLandmark.RIGHT_SHOULDER)

    draw_pose_point(shoulder_l, "shoulder_l", (0, 180, 255))
    draw_pose_point(shoulder_r, "shoulder_r", (0, 180, 255))

    if not (shoulder_l and shoulder_r):
        return

    anchor_x = (shoulder_l.x + shoulder_r.x) * 0.5
    anchor_y = (shoulder_l.y + shoulder_r.y) * 0.5

    shoulder_px = to_px(shoulder_l.x, shoulder_l.y)
    shoulder_r_px = to_px(shoulder_r.x, shoulder_r.y)
    anchor_px = to_px(anchor_x, anchor_y)

    cv2.line(frame, shoulder_px, shoulder_r_px, (160, 160, 160), 1)
    cv2.circle(frame, anchor_px, 6, (0, 0, 255), 2)
    cv2.putText(frame, "neck_anchor_est", (anchor_px[0] + 7, anchor_px[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 1)


def _draw_violin_anchor_debug_markers(frame, state: HolisticState, violin_state: ViolinState) -> None:
    h, w = frame.shape[:2]

    def to_px(x: float, y: float) -> tuple[int, int]:
        return int(x * w), int(y * h)

    shoulder_l = state.get_pose_landmark(PoseLandmark.LEFT_SHOULDER)
    ear_l = state.get_pose_landmark(PoseLandmark.LEFT_EAR)
    mouth_l = state.get_pose_landmark(PoseLandmark.MOUTH_LEFT)

    anchor_px = to_px(violin_state.anchor[0], violin_state.anchor[1])
    cv2.circle(frame, anchor_px, 8, (255, 255, 0), 2)
    cv2.putText(frame, "violin_anchor", (anchor_px[0] + 10, anchor_px[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

    if shoulder_l is not None:
        shoulder_px = to_px(shoulder_l.x, shoulder_l.y)
        cv2.line(frame, shoulder_px, anchor_px, (255, 255, 0), 1)

    if ear_l is not None and mouth_l is not None:
        ear_px = to_px(ear_l.x, ear_l.y)
        mouth_px = to_px(mouth_l.x, mouth_l.y)
        cv2.line(frame, ear_px, mouth_px, (255, 255, 0), 1)


def _draw_left_shoulder_wrist_debug(frame, state: HolisticState, violin_state: ViolinState) -> None:
    h, w = frame.shape[:2]

    shoulder_l = state.get_pose_landmark(PoseLandmark.LEFT_SHOULDER)
    wrist_l = state.get_pose_landmark(PoseLandmark.LEFT_WRIST)
    if shoulder_l is None or wrist_l is None:
        return

    shoulder_3d = (float(shoulder_l.x), float(shoulder_l.y), float(shoulder_l.z))
    wrist_3d = (float(wrist_l.x), float(wrist_l.y), float(wrist_l.z))

    shoulder_px = (int(shoulder_3d[0] * w), int(shoulder_3d[1] * h))
    wrist_px = (int(wrist_3d[0] * w), int(wrist_3d[1] * h))
    cv2.arrowedLine(frame, shoulder_px, wrist_px, (0, 165, 255), 2, tipLength=0.2)
    cv2.putText(frame, "L shoulder->wrist (3D proj)", (wrist_px[0] + 6, wrist_px[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

    arm_vec_3d = (
        wrist_3d[0] - shoulder_3d[0],
        wrist_3d[1] - shoulder_3d[1],
        wrist_3d[2] - shoulder_3d[2],
    )
    arm_len_3d = max(1e-6, math.sqrt(arm_vec_3d[0] * arm_vec_3d[0] + arm_vec_3d[1] * arm_vec_3d[1] + arm_vec_3d[2] * arm_vec_3d[2]))
    arm_dir_3d = (arm_vec_3d[0] / arm_len_3d, arm_vec_3d[1] / arm_len_3d, arm_vec_3d[2] / arm_len_3d)

    anchor_3d = violin_state.anchor
    anchor_px = (int(anchor_3d[0] * w), int(anchor_3d[1] * h))
    z_end_3d = (
        anchor_3d[0] + violin_state.neck_dir_3d[0] * arm_len_3d,
        anchor_3d[1] + violin_state.neck_dir_3d[1] * arm_len_3d,
        anchor_3d[2] + violin_state.neck_dir_3d[2] * arm_len_3d,
    )
    z_end = (int(z_end_3d[0] * w), int(z_end_3d[1] * h))

    cv2.arrowedLine(frame, anchor_px, z_end, (0, 255, 0), 2, tipLength=0.2)
    cv2.putText(frame, "violin +Z (3D proj)", (z_end[0] + 6, z_end[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

    dot_3d = max(
        -1.0,
        min(
            1.0,
            arm_dir_3d[0] * violin_state.neck_dir_3d[0]
            + arm_dir_3d[1] * violin_state.neck_dir_3d[1]
            + arm_dir_3d[2] * violin_state.neck_dir_3d[2],
        ),
    )
    angle_deg_3d = math.degrees(math.acos(dot_3d))
    dz = wrist_3d[2] - shoulder_3d[2]
    cv2.putText(frame, f"3D Z vs arm: {angle_deg_3d:.1f} deg, dz={dz:+.3f}", (anchor_px[0] + 10, anchor_px[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)


def draw_scene(
    frame,
    state: HolisticState,
    violin_profile: Optional[ViolinProfile] = None,
) -> None:
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

    if DRAW_ANCHOR_DEBUG:
        _draw_anchor_debug_markers(frame, state)

    profile = violin_profile or ViolinProfile()
    violin_state = ViolinStateEstimator().estimate(state, profile)
    if violin_state is not None:
        if DRAW_ANCHOR_DEBUG:
            _draw_violin_anchor_debug_markers(frame, state, violin_state)
            _draw_left_shoulder_wrist_debug(frame, state, violin_state)
        draw_violin_from_state(frame, profile, violin_state)


def _draw_axis_gizmo(frame, anchor_px: tuple[int, int], neck_dir_2d: tuple[float, float], right_dir_2d: tuple[float, float], up_dir_2d: tuple[float, float], scale: float = 80.0) -> None:
    """
    Draw 3D axis gizmo at anchor point showing violin orientation.
    
    Args:
        frame: Image frame to draw on
        anchor_px: Anchor point in pixel coordinates (center)
        neck_dir_2d: Normalized forward direction (Z axis, typically green)
        right_dir_2d: Normalized right direction (X axis, typically red)
        up_dir_2d: Normalized up direction (Y axis, typically blue)
        scale: Length of axis arrows in pixels
    """
    # Red arrow for right (X axis)
    right_end = (
        int(anchor_px[0] + right_dir_2d[0] * scale),
        int(anchor_px[1] + right_dir_2d[1] * scale)
    )
    cv2.arrowedLine(frame, anchor_px, right_end, (0, 0, 255), 2, tipLength=0.3)
    cv2.putText(frame, "X", (right_end[0] + 5, right_end[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    # Green arrow for neck/forward (Z axis)
    neck_end = (
        int(anchor_px[0] + neck_dir_2d[0] * scale),
        int(anchor_px[1] + neck_dir_2d[1] * scale)
    )
    cv2.arrowedLine(frame, anchor_px, neck_end, (0, 255, 0), 2, tipLength=0.3)
    cv2.putText(frame, "Z", (neck_end[0] + 5, neck_end[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    # Blue arrow for up (Y axis)
    up_end = (
        int(anchor_px[0] + up_dir_2d[0] * scale),
        int(anchor_px[1] + up_dir_2d[1] * scale)
    )
    cv2.arrowedLine(frame, anchor_px, up_end, (255, 0, 0), 2, tipLength=0.3)
    cv2.putText(frame, "Y", (up_end[0] + 5, up_end[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # Center dot
    cv2.circle(frame, anchor_px, 5, (255, 255, 255), -1)


def draw_violin_from_state(frame, violin_profile: ViolinProfile, violin_state: ViolinState) -> None:
    h, w = frame.shape[:2]

    def project_to_px(point_2d: tuple[float, float]) -> tuple[int, int]:
        return int(point_2d[0] * w), int(point_2d[1] * h)

    # origin_local = violin_profile.pnp_keypoints.chin_anchor
    origin_local = (0.0, 0.0, 0.0)  # Assuming anchor is at local origin for simplicity
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

        fingering_points = _compute_fingering_points(
            segment,
            half_step_count=DEFAULT_HALF_STEP_COUNT,
            use_fixed_string_length=USE_FIXED_STRING_LENGTH,
            fixed_string_length=FIXED_STRING_LENGTH_METERS,
        )
        prev_px = None
        for point_local in fingering_points:
            point_px = project_to_px(violin_state.transform_local_xz(point_local, origin_local))
            cv2.circle(frame, point_px, FINGERING_POINT_RADIUS_PX, FINGERING_POINT_COLOR_BGR, -1)
            if prev_px is not None:
                cv2.line(frame, prev_px, point_px, color, 1)
            prev_px = point_px

    anchor_px = project_to_px((violin_state.anchor[0], violin_state.anchor[1]))
    cv2.circle(frame, anchor_px, 8, (0, 200, 255), 2)
    cv2.putText(frame, "chin_anchor", (anchor_px[0] + 10, anchor_px[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
    
    # Draw orientation axis gizmo
    _draw_axis_gizmo(frame, anchor_px, violin_state.neck_dir_2d, violin_state.right_dir_2d, violin_state.up_dir_2d)
