from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional

import cv2
from mediapipe.python.solutions import drawing_utils, drawing_styles, holistic

import numpy as np

from framework.cv_core import (
    FeatureExtractor,
    HybridFusionEngine,
    InstrumentPoseEstimator,
    JointMeasurement,
    MediaPipeHolisticTracker,
    TemporalSmoother,
)
from framework.instruments import InstrumentModule, ViolinModule
from framework.network import UDPBroadcaster


def _load_calibration_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        logging.warning("Calibration file not found: %s. Using built-in defaults.", path)
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            logging.warning("Calibration file has invalid format. Using built-in defaults.")
            return {}
        return payload
    except Exception as exc:
        logging.warning("Failed to load calibration file %s: %s. Using built-in defaults.", path, exc)
        return {}


def _build_profiles(args) -> dict:
    payload = _load_calibration_file(args.calibration_file)
    profiles = payload.get("profiles", {}) if isinstance(payload.get("profiles", {}), dict) else {}

    violin_profile = profiles.get("violin", {}) if isinstance(profiles.get("violin", {}), dict) else {}

    if args.violin_string_width > 0:
        violin_profile["string_width"] = float(args.violin_string_width)

    return {
        "violin": violin_profile,
    }


def build_instrument(mode: str, profiles: dict) -> Optional[InstrumentModule]:
    if mode == "none":
        return None
    modules: Dict[str, InstrumentModule] = {
        "violin": ViolinModule(profile=profiles.get("violin", {})),
    }
    if mode not in modules:
        raise ValueError(f"Unknown instrument mode: {mode}")
    return modules[mode]


def _to_px(point, width: int, height: int):
    return (int(point[0] * width), int(point[1] * height))


def _draw_violin_schematic(frame, pose_data: dict) -> None:
    if pose_data is None:
        return

    h, w = frame.shape[:2]
    center = pose_data.get("center")
    neck_end = pose_data.get("neck_end")
    body_end = pose_data.get("body_end")
    chin_anchor = pose_data.get("chin_anchor")

    if center is None or neck_end is None or body_end is None:
        return

    center_px = _to_px(center, w, h)
    neck_px = _to_px(neck_end, w, h)
    body_px = _to_px(body_end, w, h)
    chin_px = _to_px(chin_anchor, w, h) if chin_anchor is not None else center_px

    # Neck
    cv2.line(frame, center_px, neck_px, (50, 220, 255), 4)
    # Body / lower bout
    cv2.line(frame, center_px, body_px, (255, 180, 0), 6)
    # Chin rest anchor
    cv2.circle(frame, chin_px, 8, (0, 200, 255), -1)
    # Body core
    cv2.circle(frame, center_px, 10, (0, 180, 255), -1)
    cv2.putText(frame, "violin body", (center_px[0] + 12, center_px[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)



    right_end = pose_data.get("right_end")
    embouchure_point = pose_data.get("embouchure_point")

    if center is None or left_end is None or right_end is None:
        return

    center_px = _to_px(center, w, h)
    left_px = _to_px(left_end, w, h)
    right_px = _to_px(right_end, w, h)
    embouchure_px = _to_px(embouchure_point, w, h) if embouchure_point is not None else center_px

def _normalize_quat(q: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(q)
    if n < 1e-8:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    return q / n


def _normalized_to_camera(point, width: int, height: int, intrinsics: Dict[str, float], depth_scale: float = 1.0, depth_base: float = 0.8):
    # Keep MediaPipe normalized coordinates (0-1 range) - this is what Unity expects
    # Just pass through x, y, z directly without camera projection
    x = float(point[0])  # 0 = left, 1 = right
    y = -float(point[1])  # 0 = top, 1 = bottom (in image space)
    z = float(point[2]) if len(point) > 2 else 0.5  # 0 = near, 1 = far
    
    # Invert Y to match world space convention (up = negative in image coords)
    y = 1.0 - y
    
    return [x, y, z]


def _build_human_measurements(state, width: int, height: int, intrinsics: Dict[str, float]) -> Dict[str, JointMeasurement]:
    out: Dict[str, JointMeasurement] = {}

    if state.pose is not None:
        for i, p in enumerate(state.pose):
            pos = _normalized_to_camera(p, width, height, intrinsics, depth_scale=0.9, depth_base=0.9)
            conf = float(np.clip(p[3], 0.0, 1.0)) if len(p) > 3 else float(state.confidences.get("pose", 0.0))
            out[f"pose_{i}"] = JointMeasurement(position=pos, rotation=[0.0, 0.0, 0.0, 1.0], confidence=conf)

    if state.left_hand is not None:
        base_conf = float(state.confidences.get("left_hand", 0.0))
        for i, p in enumerate(state.left_hand):
            pos = _normalized_to_camera(p, width, height, intrinsics, depth_scale=0.5, depth_base=0.7)
            out[f"left_{i}"] = JointMeasurement(position=pos, rotation=[0.0, 0.0, 0.0, 1.0], confidence=base_conf)

    if state.right_hand is not None:
        base_conf = float(state.confidences.get("right_hand", 0.0))
        for i, p in enumerate(state.right_hand):
            pos = _normalized_to_camera(p, width, height, intrinsics, depth_scale=0.5, depth_base=0.7)
            out[f"right_{i}"] = JointMeasurement(position=pos, rotation=[0.0, 0.0, 0.0, 1.0], confidence=base_conf)

    return out


def _quat_to_axis_up(q_in) -> tuple[list[float], list[float]]:
    q = _normalize_quat(np.asarray(q_in, dtype=np.float32))
    x, y, z, w = q

    r00 = 1 - 2 * (y * y + z * z)
    r01 = 2 * (x * y - z * w)
    r10 = 2 * (x * y + z * w)
    r11 = 1 - 2 * (x * x + z * z)
    r20 = 2 * (x * z - y * w)
    r21 = 2 * (y * z + x * w)

    axis = [float(r00), float(r10), float(r20)]
    up = [float(r01), float(r11), float(r21)]
    return axis, up


def run(args) -> None:
    tracker = MediaPipeHolisticTracker(camera_index=args.camera)
    if not tracker.is_opened():
        tracker.close()
        raise RuntimeError(
            f"Could not open camera index {args.camera}. Try --camera 1 (or another index), and close other apps using the webcam."
        )

    smoother = TemporalSmoother(window_size=args.smoothing_window, use_kalman=args.use_kalman)
    extractor = FeatureExtractor()
    fusion = HybridFusionEngine(
        base_gain=args.base_gain,
        confidence_threshold=args.confidence_threshold,
        pos_smoothing_alpha=args.pos_smoothing_alpha,
    )
    profiles = _build_profiles(args)
    instrument = build_instrument(args.instrument, profiles)
    instrument_estimator = InstrumentPoseEstimator(mode="pnp")

    broadcaster = UDPBroadcaster(ip=args.ip, port=args.port)

    if instrument:
        logging.info("Instrument module: %s", instrument.name())
    else:
        logging.info("Raw holistic tracking mode (no instrument plugin)")
    if args.flip_camera:
        logging.info("Camera flip enabled (horizontal)")
    logging.info("Broadcasting to UDP %s:%d", args.ip, args.port)
    logging.info("Press ESC in the OpenCV window to stop.")

    if args.show_cv:
        try:
            cv2.namedWindow("Holistic Tracking Pipeline", cv2.WINDOW_NORMAL)
            logging.info("OpenCV window initialized.")
        except cv2.error as exc:
            tracker.close()
            broadcaster.close()
            raise RuntimeError(
                "OpenCV GUI backend failed to initialize. Run without --show-cv, or reinstall OpenCV with GUI support."
            ) from exc

    # MediaPipe drawing utilities for visualization
    drawing_utils_mp = drawing_utils
    drawing_styles_mp = drawing_styles
    holistic_mp = holistic

    missed_frames = 0
    prev_t = time.time()
    intrinsics: Optional[Dict[str, float]] = None

    try:
        while True:
            ok, frame = tracker.read()
            if not ok:
                missed_frames += 1
                if missed_frames == 30:
                    logging.warning(
                        "No camera frames received yet. Check webcam permissions and try another index with --camera 1"
                    )
                continue
            missed_frames = 0

            if args.flip_camera:
                frame = cv2.flip(frame, 1)

            state = tracker.process(frame)
            smoothed_state = smoother.smooth(state)
            features = extractor.extract(smoothed_state)

            frame_h, frame_w = frame.shape[:2]
            if intrinsics is None:
                # Improved defaults: typical webcam has FOV ~60-70 degrees
                # This corresponds to focal length ≈ 0.7-0.8 * frame width
                fx = args.fx if args.fx > 0 else float(frame_w) * 0.7
                fy = args.fy if args.fy > 0 else float(frame_h) * 0.7
                cx = args.cx if args.cx >= 0 else float(frame_w) * 0.5
                cy = args.cy if args.cy >= 0 else float(frame_h) * 0.5
                intrinsics = {"fx": fx, "fy": fy, "cx": cx, "cy": cy}

            now_t = time.time()
            dt = max(now_t - prev_t, 1e-3)
            prev_t = now_t

            instrument_hint = None
            if instrument is not None:
                instrument_hint = instrument.estimate_pose(features)

            instrument_measurement_raw = None
            instrument_measurement = None
            if instrument is not None:
                instrument_measurement_raw = instrument_estimator.estimate(
                    frame_bgr=frame,
                    intrinsics=intrinsics,
                    instrument_name=instrument.name(),
                    hint_pose=instrument_hint,
                )
                if instrument_measurement_raw is not None:
                    instrument_measurement = JointMeasurement(
                        position=instrument_measurement_raw.position,
                        rotation=instrument_measurement_raw.rotation,
                        confidence=instrument_measurement_raw.confidence,
                    )

            human_measurements = _build_human_measurements(smoothed_state, frame_w, frame_h, intrinsics)

            hybrid_output = fusion.update(
                dt=dt,
                human_measurements=human_measurements,
                instrument_measurement=instrument_measurement,
                instrument_name=instrument.name() if instrument else "none",
            )

            instrument_interaction = None
            if instrument is not None:
                instrument_interaction = instrument.process(
                    features,
                    context={
                        "frame_width": frame_w,
                        "frame_height": frame_h,
                        "intrinsics": intrinsics,
                        "instrument_pose": hybrid_output.get("instrument", {}),
                    },
                )
                hybrid_output["instrument_interaction"] = instrument_interaction

            filtered_inst = hybrid_output["instrument"]
            inst_axis, inst_up = _quat_to_axis_up(filtered_inst["rotation"])
            instrument_pose = {
                "type": instrument.name() if instrument else "none",
                "center": filtered_inst["position"],
                "axis": inst_axis,
                "up": inst_up,
                "confidence": float(filtered_inst.get("confidence", 0.0)),
            }

            # Build raw measurement dict (use raw state, not smoothed, to avoid timing issues)
            raw_measurements = _build_human_measurements(state, frame_w, frame_h, intrinsics)
            
            # Convert to hybrid state format for broadcasting
            human_joints = {
                key: {
                    "position": meas.position,
                    "rotation": meas.rotation,
                    "confidence": meas.confidence,
                }
                for key, meas in raw_measurements.items()
            }
            
            hybrid_output = {
                "human_joints": human_joints,
                "instrument": {"position": [0, 0, 0], "rotation": [0, 0, 0, 1], "confidence": 0},
                "contacts": {},
            }
            
            broadcaster.send_hybrid_state(hybrid_output)

            if args.show_cv:
                frame.flags.writeable = True

                # Draw pose
                if smoothed_state.pose is not None:
                    # Convert back to MediaPipe format for drawing
                    from mediapipe.framework.formats import landmark_pb2

                    pose_lm = landmark_pb2.NormalizedLandmarkList()
                    for pt in smoothed_state.pose:
                        pose_lm.landmark.add(x=pt[0], y=pt[1], z=pt[2], visibility=pt[3])
                    drawing_utils_mp.draw_landmarks(
                        frame,
                        pose_lm,
                        holistic_mp.POSE_CONNECTIONS,
                        landmark_drawing_spec=drawing_styles_mp.get_default_pose_landmarks_style(),
                    )

                # Draw hands
                if smoothed_state.left_hand is not None:
                    left_hand_lm = landmark_pb2.NormalizedLandmarkList()
                    for pt in smoothed_state.left_hand:
                        left_hand_lm.landmark.add(x=pt[0], y=pt[1], z=pt[2])
                    drawing_utils_mp.draw_landmarks(
                        frame,
                        left_hand_lm,
                        holistic_mp.HAND_CONNECTIONS,
                        landmark_drawing_spec=drawing_styles_mp.get_default_hand_landmarks_style(),
                    )

                if smoothed_state.right_hand is not None:
                    right_hand_lm = landmark_pb2.NormalizedLandmarkList()
                    for pt in smoothed_state.right_hand:
                        right_hand_lm.landmark.add(x=pt[0], y=pt[1], z=pt[2])
                    drawing_utils_mp.draw_landmarks(
                        frame,
                        right_hand_lm,
                        holistic_mp.HAND_CONNECTIONS,
                        landmark_drawing_spec=drawing_styles_mp.get_default_hand_landmarks_style(),
                    )

                if instrument_pose is not None:
                    confidence = instrument_pose["confidence"]

                    if instrument is not None and instrument.name() == "violin":
                        _draw_violin_schematic(frame, instrument_hint if instrument_hint is not None else instrument_pose)

                # Keep selfie-style preview, but draw labels after flip so text stays readable.
                display_frame = cv2.flip(frame, 1)

                if instrument_pose is not None:
                    cv2.putText(
                        display_frame,
                        f"Instrument: {instrument_pose['type']} conf={confidence:.2f}",
                        (12, 58),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 220, 220),
                        2,
                    )

                instrument_source = instrument_measurement_raw.source if instrument_measurement_raw is not None else "prediction"
                inst_conf = float(filtered_inst.get("confidence", 0.0))
                contacts = hybrid_output.get("contacts", {})
                contact_labels = [f"{k}={v:.03f}" for k, v in list(contacts.items())[:3]]

                cv2.putText(
                    display_frame,
                    f"Hybrid conf: pose={smoothed_state.confidences.get('pose', 0.0):.2f} face={smoothed_state.confidences.get('face', 0.0):.2f}",
                    (12, 84),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 200, 0),
                    2,
                )
                cv2.putText(
                    display_frame,
                    f"Instrument 6DoF: src={instrument_source} conf={inst_conf:.2f}",
                    (12, 108),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (255, 200, 0),
                    2,
                )
                if contact_labels:
                    cv2.putText(
                        display_frame,
                        "Contacts: " + " | ".join(contact_labels),
                        (12, 132),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.46,
                        (120, 255, 120),
                        1,
                    )

                if instrument_interaction is not None and instrument is not None:
                    if instrument.name() == "violin":
                        left_state = instrument_interaction.get("left_hand", {})
                        right_state = instrument_interaction.get("right_hand", {})
                        
                        # Main violin info
                        cv2.putText(
                            display_frame,
                            f"Violin: string={left_state.get('string', '?')} pos={left_state.get('finger_position', 0)} bow={right_state.get('bow_direction', '?')} speed={right_state.get('bow_speed', 0.0):.2f}",
                            (12, 180),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.46,
                            (255, 230, 120),
                            1,
                        )
                        
                        # NEW: Finger detection info
                        active_finger = left_state.get('active_finger', 0)
                        note = left_state.get('note', '?')
                        finger_names = {0: 'open', 1: 'index', 2: 'middle', 3: 'ring', 4: 'pinky'}
                        
                        # Display current note and active finger
                        cv2.putText(
                            display_frame,
                            f"NOTE: {note}  FINGER: {finger_names.get(active_finger, '?')} ({active_finger})",
                            (12, 228),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (100, 255, 100) if active_finger > 0 else (200, 200, 200),
                            2,
                        )
                        
                        # Display all finger states
                        finger_states = left_state.get('finger_states', {})
                        contact_states = finger_states.get('contact_states', {})
                        
                        if contact_states:
                            # Build finger state display
                            state_display = ""
                            state_colors = {'lifted': (150, 150, 150), 'touching': (255, 255, 0), 'pressed': (0, 255, 0)}
                            
                            # Index finger
                            idx_state = contact_states.get('index', 'lifted')
                            idx_color = state_colors.get(idx_state, (150, 150, 150))
                            cv2.putText(
                                display_frame,
                                f"Index: {idx_state}",
                                (12, 252),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.42,
                                idx_color,
                                1,
                            )
                            
                            # Middle finger
                            mid_state = contact_states.get('middle', 'lifted')
                            mid_color = state_colors.get(mid_state, (150, 150, 150))
                            cv2.putText(
                                display_frame,
                                f"Middle: {mid_state}",
                                (150, 252),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.42,
                                mid_color,
                                1,
                            )
                            
                            # Ring finger
                            ring_state = contact_states.get('ring', 'lifted')
                            ring_color = state_colors.get(ring_state, (150, 150, 150))
                            cv2.putText(
                                display_frame,
                                f"Ring: {ring_state}",
                                (280, 252),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.42,
                                ring_color,
                                1,
                            )
                            
                            # Pinky finger
                            pinky_state = contact_states.get('pinky', 'lifted')
                            pinky_color = state_colors.get(pinky_state, (150, 150, 150))
                            cv2.putText(
                                display_frame,
                                f"Pinky: {pinky_state}",
                                (410, 252),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.42,
                                pinky_color,
                                1,
                            )
                    
                cv2.putText(
                    display_frame,
                    f"Stable joints: {len(hybrid_output.get('human_joints', {}))} | frame=cam-space",
                    (12, 204),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.46,
                    (120, 255, 120),
                    1,
                )

                label = instrument.name() if instrument else "raw"
                cv2.putText(
                    display_frame,
                    f"Mode: {label} [play-pnp] | UDP {args.ip}:{args.port}",
                    (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (30, 220, 30),
                    2,
                )
                cv2.imshow("Holistic Tracking Pipeline", display_frame)

            if args.show_cv:
                key = cv2.waitKey(5) & 0xFF
                if key == 27:
                    break

    finally:
        tracker.close()
        broadcaster.close()
        cv2.destroyAllWindows()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Hybrid human+instrument tracking with Holistic + 6DoF fusion (UDP broadcast)"
    )
    parser.add_argument("--instrument", choices=["none", "violin"], default="none")
    parser.add_argument(
        "--calibration-file",
        default="config/instrument_profiles.json",
        help="Path to JSON calibration profile file.",
    )
    parser.add_argument("--violin-string-width", type=float, default=-1.0)
    parser.add_argument("--fx", type=float, default=-1.0, help="Camera focal length fx in pixels. Defaults to frame width.")
    parser.add_argument("--fy", type=float, default=-1.0, help="Camera focal length fy in pixels. Defaults to frame height.")
    parser.add_argument("--cx", type=float, default=-1.0, help="Camera principal point cx in pixels. Defaults to frame center.")
    parser.add_argument("--cy", type=float, default=-1.0, help="Camera principal point cy in pixels. Defaults to frame center.")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--flip-camera", action="store_true")
    parser.add_argument("--smoothing-window", type=int, default=5)
    parser.add_argument("--use-kalman", action="store_true")
    parser.add_argument("--base-gain", type=float, default=0.45)
    parser.add_argument("--confidence-threshold", type=float, default=0.2)
    parser.add_argument("--pos-smoothing-alpha", type=float, default=0.75)
    parser.add_argument("--show-cv", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    run(args)
