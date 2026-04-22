from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


Vec3 = tuple[float, float, float]
Vec3Pair = tuple[Vec3, Vec3]


class ViolinPnpKeypoints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chin_anchor: Vec3 = (-0.0323, 0.0, 0.01385)
    neck_end: Vec3 = (0.0, 0.00778, 0.41379)


class ViolinStrings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    G: Vec3Pair = ((-0.0141, 0.05244, 0.13621), (-0.00641, 0.00778, 0.41379))
    D: Vec3Pair = ((-0.00548, 0.05491, 0.13621), (-0.00227, 0.00778, 0.41379))
    A: Vec3Pair = ((0.00548, 0.05491, 0.13621), (0.00227, 0.00778, 0.41379))
    E: Vec3Pair = ((0.0141, 0.05244, 0.13621), (0.00641, 0.00778, 0.41379))


class ViolinGeometryProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    strings: ViolinStrings = Field(default_factory=ViolinStrings)
    body_outline: list[Vec3] = Field(
        default_factory=lambda: [
            (0.0, 0.0, 0.0),
            (0.0646, 0.0, 0.0277),
            (0.0608, 0.0, 0.267),
            (0.0, 0.0, 0.3038),
            (-0.0608, 0.0, 0.267),
            (-0.0646, 0.0, 0.0277),
        ]
    )
    bow_contact: Optional[Vec3] = None


class ViolinProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pnp_keypoints: ViolinPnpKeypoints = Field(default_factory=ViolinPnpKeypoints)
    geometry: ViolinGeometryProfile = Field(default_factory=ViolinGeometryProfile)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ViolinProfile":
        return cls.model_validate(payload)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ViolinProfile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def to_runtime_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class InstrumentProfiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    violin: ViolinProfile = Field(default_factory=ViolinProfile)


class InstrumentProfilesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: InstrumentProfiles = Field(default_factory=InstrumentProfiles)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "InstrumentProfilesFile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)


def load_violin_profile(path: str | Path) -> ViolinProfile:
    """Load profiles JSON and return only the violin profile."""
    return InstrumentProfilesFile.from_json_file(path).profiles.violin
