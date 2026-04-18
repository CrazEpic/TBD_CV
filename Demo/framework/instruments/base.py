from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class InstrumentModule(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def process(self, features: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Input: shared CV features
        Context: runtime pose/camera information
        Output: instrument-specific interaction state
        """
        raise NotImplementedError

    def estimate_pose(self, features: Dict[str, Any]):
        """Return an estimated instrument pose derived from the human pose."""
        return None
