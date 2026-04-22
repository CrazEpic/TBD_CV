from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Vec3 = tuple[float, float, float]
Quat4 = tuple[float, float, float, float]


class HybridJointState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Vec3
    rotation: Quat4 = (0.0, 0.0, 0.0, 1.0)
    confidence: float = 0.0


class HybridInstrumentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Vec3
    rotation: Quat4 = (0.0, 0.0, 0.0, 1.0)
    confidence: float = 0.0


class HybridStateV2Data(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_joints: dict[str, HybridJointState] = Field(default_factory=dict)
    instrument: HybridInstrumentState | None = None
    contacts: dict[str, float] = Field(default_factory=dict)

    def to_udp_payload(self) -> dict:
        return {
            "type": "hybrid_state_v2",
            "data": self.model_dump(mode="python"),
        }


class HybridStateV2Packet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["hybrid_state_v2"] = "hybrid_state_v2"
    data: HybridStateV2Data

    def to_udp_payload(self) -> dict:
        return self.model_dump(mode="python")

    def to_udp_json(self) -> str:
        return json.dumps(self.to_udp_payload(), separators=(",", ":"))

    def to_udp_bytes(self) -> bytes:
        return self.to_udp_json().encode("utf-8")


def make_hybrid_state_v2_packet(data: HybridStateV2Data) -> HybridStateV2Packet:
    return HybridStateV2Packet(data=data)
