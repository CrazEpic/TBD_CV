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
    VIOLIN_PNP_POINTS = {
        "body_center": np.array([0.0, 0.0, 0.0], dtype=np.float64),      # Body center (origin)
        "neck_end": np.array([0.33, 0.0, 0.0], dtype=np.float64),         # Scroll end of neck (compressed)
        "body_bottom": np.array([0.0, -0.14, 0.0], dtype=np.float64),     # Lower bout of body
        "chin_anchor": np.array([-0.05, 0.08, 0.0], dtype=np.float64),    # Chin rest contact point
    }

    # Extended geometry: strings and positions for detailed visualization
    VIOLIN_STRINGS = {
        "G": np.array([0.17, 0.03, 0.0], dtype=np.float64),          # G string (midway along neck)
        "D": np.array([0.17, 0.01, 0.0], dtype=np.float64),          # D string
        "A": np.array([0.17, -0.01, 0.0], dtype=np.float64),         # A string
        "E": np.array([0.17, -0.03, 0.0], dtype=np.float64),         # E string
    }

    # Body outline points (for visualization)
    VIOLIN_BODY_OUTLINE = [
        np.array([0.02, 0.08, 0.03], dtype=np.float64),   # Upper bout left
        np.array([0.02, 0.08, -0.03], dtype=np.float64),  # Upper bout right
        np.array([0.08, 0.02, 0.04], dtype=np.float64),   # Middle left
        np.array([0.08, 0.02, -0.04], dtype=np.float64),  # Middle right
        np.array([0.02, -0.12, 0.03], dtype=np.float64),  # Bottom left
        np.array([0.02, -0.12, -0.03], dtype=np.float64), # Bottom right
    ]

    # Fingerboard points (along the compressed neck)
    VIOLIN_FINGERBOARD = [
        np.array([0.05, -0.01, 0.0], dtype=np.float64),   # Fingerboard start (near body)
        np.array([0.17, -0.005, 0.0], dtype=np.float64),  # Fingerboard middle
        np.array([0.33, 0.0, 0.0], dtype=np.float64),     # Fingerboard end (scroll)
    ]
    
    # Bow reference point (where bow hair contacts strings)
    BOW_CONTACT_POINT = np.array([-0.05, 0.0, 0.0], dtype=np.float64)  # Near chin rest

    @staticmethod
    def get_pnp_points() -> Tuple[np.ndarray, List[str]]:
        """
        Get the 4 key points used for PnP solver.

        Returns:
            Tuple of (object_points [4x3], point_names [4])
        """
        points = []
        names = []
        for name in ["body_center", "neck_end", "body_bottom", "chin_anchor"]:
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

        body_outline = np.array(ViolinGeometry.VIOLIN_BODY_OUTLINE, dtype=np.float64)
        fingerboard = np.array(ViolinGeometry.VIOLIN_FINGERBOARD, dtype=np.float64)
        bow_contact = np.array([ViolinGeometry.BOW_CONTACT_POINT], dtype=np.float64)

        return {
            "pnp_points": pnp_pts,
            "strings": strings_array,
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

        return output
