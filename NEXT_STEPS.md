# Project Status and Next Steps

## Current System Overview

This project is currently a real-time play workflow for instrument interaction using:

- MediaPipe Holistic for human landmarks (pose, hands, face)
- Instrument pose estimation with solvePnP (6DoF)
- Hybrid temporal fusion for stabilized joints and instrument pose
- Instrument interaction logic for:
  - Violin fingering and bowing
- UDP JSON streaming to Unity with packet type hybrid_state_v2

The active runtime path is centered in:

- [Demo/run_realtime_framework.py](Demo/run_realtime_framework.py)
- [Demo/framework/cv_core/instrument_6dof.py](Demo/framework/cv_core/instrument_6dof.py)
- [Demo/framework/cv_core/hybrid_fusion.py](Demo/framework/cv_core/hybrid_fusion.py)
- [Demo/framework/instruments/violin.py](Demo/framework/instruments/violin.py)
- [Demo/framework/network/udp_broadcaster.py](Demo/framework/network/udp_broadcaster.py)
- [UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs](UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs)
- [UnityProject/Assets/_Project/Scripts/AvatarController.cs](UnityProject/Assets/_Project/Scripts/AvatarController.cs)

## Calibration Profiles

Profile defaults now live in:

- [Demo/config/instrument_profiles.json](Demo/config/instrument_profiles.json)

Supported profile values:

- Violin:
  - string_centers
  - string_width
  - position_bins
  - bow_pressure_center_y
  - bow_pressure_half_width

## How To Run

From repository root:

1. Install dependencies

   pip install -r requirements.txt

2. Run violin mode with CV window

   python Demo/run_realtime_framework.py --instrument violin --show-cv

3. Optional camera intrinsics override

   python Demo/run_realtime_framework.py --instrument violin --fx 1100 --fy 1100 --cx 640 --cy 360 --show-cv

4. Optional calibration file override

   python Demo/run_realtime_framework.py --instrument violin --show-cv --calibration-file Demo/config/instrument_profiles.json

5. Optional quick tuning overrides from CLI

   python Demo/run_realtime_framework.py --instrument violin --show-cv --violin-string-width 0.022

## Running With Unity

1. Start the Python runtime first.
2. Open Unity project in [UnityProject](UnityProject).
3. Enter Play mode.
4. Verify avatar and instrument behavior update from UDP stream.

Current UDP payload includes:

- human_joints
- instrument
- contacts
- instrument_interaction

## Test Plan (Practical)

### Smoke Test

- Launch Python runtime for violin.
- Confirm no immediate runtime errors.
- Confirm OpenCV overlay updates continuously.
- Confirm Unity avatar responds in Play mode.

### Violin Validation

- Test open string and progressive finger positions.
- Verify string selection consistency when crossing strings.
- Test slow and fast bow direction changes.
- Tune string_width and position_bins if string switching is too sensitive or too sticky.

### Repeatable Scenario Set

Capture at least three short runs:

- steady hold
- controlled transitions
- fast transitions

Keep lighting and camera position consistent across runs.

## Suggested Immediate Next Steps

1. Add lightweight frame logger for instrument_interaction and confidence values.
   - Output CSV or JSONL per frame for objective tuning.

2. Add explicit confidence gating to interaction outputs.
   - Hold previous stable state during low-confidence windows.

3. Add profile presets for camera distance scenarios.
   - Example: near, mid, far presets in profile file.

4. Add quick performance benchmark mode.
   - Report FPS and per-stage processing times.

5. Add Unity-side debug panel.
   - Show live values for violin string, finger_position, bow_direction, and confidence.

## Known Limitations

- Instrument pose still depends on human-derived hint anchors before PnP.
- Monocular ambiguity can affect orientation under occlusion.
- Accuracy depends strongly on camera framing, lighting, and performer distance.

## Maintenance Notes

- Keep this file updated whenever run flags, payload schema, or profile keys change.
- Update [README.md](README.md) after major workflow changes to stay aligned.
