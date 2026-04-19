"""
Violin 3D geometry model for pose estimation and visualization.

Defines the violin model points used in PnP and provides methods to:
1. Get the violin's 3D key points (strings, fingerboard, body, neck, chin rest)
2. Transform them using the estimated 6DoF pose
3. Return them in a format suitable for broadcasting to Unity
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import cv2


class ViolinGeometry:
    """Defines and manages violin 3D geometry for pose estimation."""

    # Violin model in local coordinate frame (cm)
    # Origin at violin body center
    # X: along neck toward scroll
    # Y: up (toward chin rest)
    # Z: lateral (toward bow arm)

    # Key points on violin for PnP solver
    DEFAULT_VIOLIN_PNP_POINTS = {
        "center": np.array([0.0, 0.0, 0.0], dtype=np.float64),      # Body center (origin)
        "neck_end": np.array([0.33, 0.0, 0.0], dtype=np.float64),         # Scroll end of neck (compressed)
        "body_end": np.array([0.0, -0.14, 0.0], dtype=np.float64),     # Lower bout of body
        "chin_anchor": np.array([-0.05, 0.08, 0.0], dtype=np.float64),    # Chin rest contact point
    }

    VIOLIN_PNP_POINTS = {
        k: v.copy() for k, v in DEFAULT_VIOLIN_PNP_POINTS.items()
    }

    DEFAULT_VIOLIN_STRINGS = {
        "G": np.array([0.17, 0.03, 0.0], dtype=np.float64),
        "D": np.array([0.17, 0.01, 0.0], dtype=np.float64),
        "A": np.array([0.17, -0.01, 0.0], dtype=np.float64),
        "E": np.array([0.17, -0.03, 0.0], dtype=np.float64),
    }

    DEFAULT_VIOLIN_STRING_SEGMENTS = {
        "G": (
            np.array([0.05, 0.03, 0.0], dtype=np.float64),
            np.array([0.33, 0.03, 0.0], dtype=np.float64),
        ),
        "D": (
            np.array([0.05, 0.01, 0.0], dtype=np.float64),
            np.array([0.33, 0.01, 0.0], dtype=np.float64),
        ),
        "A": (
            np.array([0.05, -0.01, 0.0], dtype=np.float64),
            np.array([0.33, -0.01, 0.0], dtype=np.float64),
        ),
        "E": (
            np.array([0.05, -0.03, 0.0], dtype=np.float64),
            np.array([0.33, -0.03, 0.0], dtype=np.float64),
        ),
    }

    # Extended geometry: strings and positions for detailed visualization
    VIOLIN_STRINGS = {
        k: v.copy() for k, v in DEFAULT_VIOLIN_STRINGS.items()
    }
    VIOLIN_STRING_SEGMENTS = {
        k: (v[0].copy(), v[1].copy()) for k, v in DEFAULT_VIOLIN_STRING_SEGMENTS.items()
    }

    # Body outline points (for visualization)
    DEFAULT_VIOLIN_BODY_OUTLINE = [
        np.array([0.02, 0.08, 0.03], dtype=np.float64),   # Upper bout left
        np.array([0.02, 0.08, -0.03], dtype=np.float64),  # Upper bout right
        np.array([0.08, 0.02, 0.04], dtype=np.float64),   # Middle left
        np.array([0.08, 0.02, -0.04], dtype=np.float64),  # Middle right
        np.array([0.02, -0.12, 0.03], dtype=np.float64),  # Bottom left
        np.array([0.02, -0.12, -0.03], dtype=np.float64), # Bottom right
    ]

    VIOLIN_BODY_OUTLINE = [pt.copy() for pt in DEFAULT_VIOLIN_BODY_OUTLINE]

    # Fingerboard points (along the compressed neck)
    DEFAULT_VIOLIN_FINGERBOARD = [
        np.array([0.05, -0.01, 0.0], dtype=np.float64),   # Fingerboard start (near body)
        np.array([0.17, -0.005, 0.0], dtype=np.float64),  # Fingerboard middle
        np.array([0.33, 0.0, 0.0], dtype=np.float64),     # Fingerboard end (scroll)
    ]
    VIOLIN_FINGERBOARD = [pt.copy() for pt in DEFAULT_VIOLIN_FINGERBOARD]
    
    # Bow reference point (where bow hair contacts strings)
    DEFAULT_BOW_CONTACT_POINT = np.array([-0.05, 0.0, 0.0], dtype=np.float64)
    BOW_CONTACT_POINT = DEFAULT_BOW_CONTACT_POINT.copy()  # Near chin rest

    VIOLIN_SUPPLEMENTARY_KEYPOINTS: Dict[str, np.ndarray] = {}

    @classmethod
    def configure_from_profile(cls, profile: Dict[str, any] | None) -> None:
        """Override default PnP model points from violin profile when available."""
        cls.VIOLIN_PNP_POINTS = {
            k: v.copy() for k, v in cls.DEFAULT_VIOLIN_PNP_POINTS.items()
        }
        cls.VIOLIN_STRINGS = {
            k: v.copy() for k, v in cls.DEFAULT_VIOLIN_STRINGS.items()
        }
        cls.VIOLIN_STRING_SEGMENTS = {
            k: (v[0].copy(), v[1].copy()) for k, v in cls.DEFAULT_VIOLIN_STRING_SEGMENTS.items()
        }
        cls.VIOLIN_BODY_OUTLINE = [pt.copy() for pt in cls.DEFAULT_VIOLIN_BODY_OUTLINE]
        cls.VIOLIN_FINGERBOARD = [pt.copy() for pt in cls.DEFAULT_VIOLIN_FINGERBOARD]
        cls.BOW_CONTACT_POINT = cls.DEFAULT_BOW_CONTACT_POINT.copy()
        cls.VIOLIN_SUPPLEMENTARY_KEYPOINTS = {}

        if not isinstance(profile, dict):
            return

        pnp = profile.get("pnp_keypoints", {})
        if not isinstance(pnp, dict):
            return

        key_candidates = {
            "center": ["center", "body_center"],
            "neck_end": ["neck_end"],
            "body_end": ["body_end", "body_bottom"],
            "chin_anchor": ["chin_anchor"],
        }

        for dst_key, src_candidates in key_candidates.items():
            value = None
            for src_key in src_candidates:
                candidate = pnp.get(src_key)
                if isinstance(candidate, (list, tuple)) and len(candidate) == 3:
                    value = candidate
                    break

            if not (isinstance(value, (list, tuple)) and len(value) == 3):
                continue

            try:
                cls.VIOLIN_PNP_POINTS[dst_key] = np.array(
                    [float(value[0]), float(value[1]), float(value[2])],
                    dtype=np.float64,
                )
            except (TypeError, ValueError):
                continue

        geometry = profile.get("geometry", {})
        if not isinstance(geometry, dict):
            return

        strings = geometry.get("strings", {})
        if isinstance(strings, dict):
            for name in ["G", "D", "A", "E"]:
                value = strings.get(name)
                parsed = cls._parse_vec3(value)
                if parsed is not None:
                    cls.VIOLIN_STRINGS[name] = parsed
                    continue

                parsed_pair = cls._parse_vec3_pair(value)
                if parsed_pair is not None:
                    p1, p2 = parsed_pair
                    cls.VIOLIN_STRING_SEGMENTS[name] = (p1, p2)
                    cls.VIOLIN_STRINGS[name] = ((p1 + p2) * 0.5).astype(np.float64)

        body_outline = geometry.get("body_outline")
        parsed_outline = cls._parse_vec3_list(body_outline)
        if parsed_outline is not None and len(parsed_outline) >= 3:
            cls.VIOLIN_BODY_OUTLINE = parsed_outline

        fingerboard = geometry.get("fingerboard")
        parsed_fingerboard = cls._parse_vec3_list(fingerboard)
        if parsed_fingerboard is not None and len(parsed_fingerboard) >= 2:
            cls.VIOLIN_FINGERBOARD = parsed_fingerboard

        bow_contact = cls._parse_vec3(geometry.get("bow_contact"))
        if bow_contact is not None:
            cls.BOW_CONTACT_POINT = bow_contact

        supplementary = geometry.get("supplementary_keypoints", {})
        if isinstance(supplementary, dict):
            for name, value in supplementary.items():
                parsed = cls._parse_vec3(value)
                if parsed is not None:
                    cls.VIOLIN_SUPPLEMENTARY_KEYPOINTS[str(name)] = parsed

    @staticmethod
    def _parse_vec3(value) -> np.ndarray | None:
        if not (isinstance(value, (list, tuple)) and len(value) == 3):
            return None
        try:
            return np.array([float(value[0]), float(value[1]), float(value[2])], dtype=np.float64)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_vec3_list(cls, value) -> List[np.ndarray] | None:
        if not isinstance(value, list):
            return None

        parsed: List[np.ndarray] = []
        for item in value:
            vec = cls._parse_vec3(item)
            if vec is None:
                return None
            parsed.append(vec)
        return parsed

    @classmethod
    def _parse_vec3_pair(cls, value) -> Tuple[np.ndarray, np.ndarray] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        p1 = cls._parse_vec3(value[0])
        p2 = cls._parse_vec3(value[1])
        if p1 is None or p2 is None:
            return None
        return p1, p2

    @staticmethod
    def get_pnp_points() -> Tuple[np.ndarray, List[str]]:
        """
        Get the 4 key points used for PnP solver.

        Returns:
            Tuple of (object_points [4x3], point_names [4])
        """
        points = []
        names = []
        for name in ["center", "neck_end", "body_end", "chin_anchor"]:
            points.append(ViolinGeometry.VIOLIN_PNP_POINTS[name])
            names.append(name)
        return np.array(points, dtype=np.float64), names

    @staticmethod
    def get_all_geometry_points() -> Dict[str, np.ndarray]:
        """
        Get all violin geometry points for visualization and broadcasting.

        Returns:
            Dict with keys: "pnp_points", "strings", "body_outline", "fingerboard", "bow_contact"
            Each value is an array of 3D points
        """
        pnp_pts, _ = ViolinGeometry.get_pnp_points()

        # String endpoints (strings go from body forward along fingerboard)
        strings_array = np.array(
            [ViolinGeometry.VIOLIN_STRINGS[s] for s in ["G", "D", "A", "E"]],
            dtype=np.float64
        )

        string_segments = []
        for s in ["G", "D", "A", "E"]:
            p1, p2 = ViolinGeometry.VIOLIN_STRING_SEGMENTS[s]
            string_segments.append(p1)
            string_segments.append(p2)
        string_segments_array = np.array(string_segments, dtype=np.float64)

        body_outline = np.array(ViolinGeometry.VIOLIN_BODY_OUTLINE, dtype=np.float64)
        fingerboard = np.array(ViolinGeometry.VIOLIN_FINGERBOARD, dtype=np.float64)
        bow_contact = np.array([ViolinGeometry.BOW_CONTACT_POINT], dtype=np.float64)

        return {
            "pnp_points": pnp_pts,
            "strings": strings_array,
            "string_segments": string_segments_array,
            "body_outline": body_outline,
            "fingerboard": fingerboard,
            "bow_contact": bow_contact,
        }

    @staticmethod
    def transform_points(
        object_points: np.ndarray,
        rvec: np.ndarray,
        tvec: np.ndarray,
        intrinsics: Dict[str, float] | None = None,
    ) -> Tuple[np.ndarray, np.ndarray | None]:
        """
        Transform object points using rotation and translation vectors.

        Args:
            object_points: [N, 3] array of 3D points in object frame
            rvec: Rotation vector (3,)
            tvec: Translation vector (3,)
            intrinsics: Camera intrinsics (optional, for reprojection check)

        Returns:
            Tuple of (transformed_points_3d [N, 3], projected_2d [N, 2] or None)
        """
        # Convert to rotation matrix
        rot_matrix, _ = cv2.Rodrigues(rvec)

        # Transform: p_world = R @ p_object + t
        transformed = np.dot(object_points, rot_matrix.T) + tvec.reshape(1, 3)

        # Optionally project to 2D
        projected_2d = None
        if intrinsics is not None:
            k = np.array(
                [
                    [intrinsics.get("fx", 0), 0.0, intrinsics.get("cx", 0)],
                    [0.0, intrinsics.get("fy", 0), intrinsics.get("cy", 0)],
                    [0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
            d = np.zeros((4, 1), dtype=np.float64)
            proj, _ = cv2.projectPoints(object_points, rvec, tvec, k, d)
            projected_2d = proj.reshape(-1, 2)

        return transformed.astype(np.float32), projected_2d

    @staticmethod
    def build_violin_output(
        rvec: np.ndarray,
        tvec: np.ndarray,
        intrinsics: Dict[str, float] | None = None,
    ) -> Dict[str, any]:
        """
        Build complete violin geometry output for broadcasting to Unity.

        Args:
            rvec: Rotation vector from PnP
            tvec: Translation vector from PnP
            intrinsics: Camera intrinsics (optional)

        Returns:
            Dict containing:
            - "pnp_points": 3D positions of PnP reference points
            - "strings": 3D endpoints of strings (G, D, A, E)
            - "body_outline": 3D body outline points
            - "fingerboard": 3D fingerboard points
            - "projected_2d": 2D projections (if intrinsics provided)
        """
        geometry = ViolinGeometry.get_all_geometry_points()
        output = {}

        for geom_name, points in geometry.items():
            transformed, projected = ViolinGeometry.transform_points(
                points, rvec, tvec, intrinsics
            )
            output[geom_name] = transformed.tolist()
            if projected is not None:
                output[f"{geom_name}_2d"] = projected.tolist()

        if ViolinGeometry.VIOLIN_SUPPLEMENTARY_KEYPOINTS:
            names = sorted(ViolinGeometry.VIOLIN_SUPPLEMENTARY_KEYPOINTS.keys())
            sup_points = np.array(
                [ViolinGeometry.VIOLIN_SUPPLEMENTARY_KEYPOINTS[n] for n in names],
                dtype=np.float64,
            )
            transformed, projected = ViolinGeometry.transform_points(
                sup_points,
                rvec,
                tvec,
                intrinsics,
            )

            output["supplementary_keypoints"] = {
                name: transformed[i].tolist() for i, name in enumerate(names)
            }
            if projected is not None:
                output["supplementary_keypoints_2d"] = {
                    name: projected[i].tolist() for i, name in enumerate(names)
                }

        return output
