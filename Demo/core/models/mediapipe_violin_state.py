from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict

from core.models.mediapipe_holistic_state import HandLandmark, HolisticState, PoseLandmark
from core.models.violin import ViolinProfile


Vec3 = tuple[float, float, float]


class ViolinState(BaseModel):
	model_config = ConfigDict(extra="forbid")

	anchor: Vec3
	neck_dir_2d: tuple[float, float]
	right_dir_2d: tuple[float, float]
	model_scale: float
	confidence: float

	def transform_local_xz(self, point_local: tuple[float, float, float], origin_local: tuple[float, float, float]) -> tuple[float, float]:
		dx = float(point_local[0] - origin_local[0]) * self.model_scale
		dz = float(point_local[2] - origin_local[2]) * self.model_scale

		x = self.anchor[0] + self.right_dir_2d[0] * dx + self.neck_dir_2d[0] * dz
		y = self.anchor[1] + self.right_dir_2d[1] * dx + self.neck_dir_2d[1] * dz
		return (x, y)


class ViolinStateEstimator:
	"""Estimate a simple violin pose from holistic pose + left hand landmarks."""

	def __init__(self) -> None:
		pass

	def estimate(self, holistic: HolisticState, profile: ViolinProfile) -> Optional[ViolinState]:
		mouth_l = holistic.get_pose_landmark(PoseLandmark.MOUTH_LEFT)
		shoulder_l = holistic.get_pose_landmark(PoseLandmark.LEFT_SHOULDER)

		if not (mouth_l and shoulder_l):
			return None

		mouth_left = _pt(mouth_l)
		shoulder_left = _pt(shoulder_l)
		anchor = _mid(mouth_left, shoulder_left)

		left_hand_conf = float(holistic.confidences.get("left_hand", 0.0))
		pose_conf = float(holistic.confidences.get("pose", 0.0))

		left_target = None
		index_mcp = holistic.get_left_hand_landmark(HandLandmark.INDEX_FINGER_MCP)
		thumb_mcp = holistic.get_left_hand_landmark(HandLandmark.THUMB_MCP)
		if index_mcp is not None and thumb_mcp is not None:
			left_target = _mid(_pt(index_mcp), _pt(thumb_mcp))
		elif holistic.get_left_hand_landmark(HandLandmark.WRIST) is not None:
			left_target = _pt(holistic.get_left_hand_landmark(HandLandmark.WRIST))
		else:
			left_wrist_pose = holistic.get_pose_landmark(PoseLandmark.LEFT_WRIST)
			if left_wrist_pose is not None:
				left_target = _pt(left_wrist_pose)

		if left_target is None:
			return None

		vx = left_target[0] - anchor[0]
		vy = left_target[1] - anchor[1]
		vlen = math.sqrt(vx * vx + vy * vy)
		if vlen < 1e-6:
			return None

		neck_dir_2d = (vx / vlen, vy / vlen)
		right_dir_2d = (-neck_dir_2d[1], neck_dir_2d[0])

		_ = profile

		# Keep the violin at authored scale from JSON (meters) in this simplified pass.
		model_scale = 1.0

		confidence = max(0.0, min(1.0, 0.6 * pose_conf + 0.4 * left_hand_conf))

		return ViolinState(
			anchor=anchor,
			neck_dir_2d=neck_dir_2d,
			right_dir_2d=right_dir_2d,
			model_scale=model_scale,
			confidence=confidence,
		)


def _pt(p) -> Vec3:
	return (float(p.x), float(p.y), float(p.z))


def _mid(a: Vec3, b: Vec3) -> Vec3:
	return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)
