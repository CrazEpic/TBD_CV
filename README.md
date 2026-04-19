# TBD_CV

pip install mediapipe
pip install opencv-python
pip3 install torch torchvision --index-url <https://download.pytorch.org/whl/cu128>
pip install numpy matplotlib

python -m ensurepip --upgrade
python -m pip debug --verbose
<https://pypi.org/project/mediapipe/0.10.21/#mediapipe-0.10.21-cp312-cp312-win_amd64.whl>
<https://www.python.org/downloads/release/python-31210/>

<https://univrm.com/>
VRM 1.0
<!-- 
Unity Registry
Animation Rigging -->

Real-time hand tracking for VRM avatars with a modular instrument plugin layer, built on top of your existing UDP pipeline.

Now includes a hybrid Holistic + 6DoF fusion pipeline:

- Human tracking: body + hands + face landmarks (confidence-aware)
- Instrument tracking: solvePnP-based 6DoF estimation
- Unified camera-frame state filtering (position/velocity/quaternion/angular velocity)
- Hand-instrument constraint enforcement and occlusion prediction

## Python Layout (Under Demo)

- [Demo/run_realtime_framework.py](Demo/run_realtime_framework.py): modular UDP runtime entrypoint
- [Demo/framework/cv_core/hand_tracking.py](Demo/framework/cv_core/hand_tracking.py): hand tracking core
- [Demo/framework/cv_core/feature_extraction.py](Demo/framework/cv_core/feature_extraction.py): feature extraction
- [Demo/framework/cv_core/smoothing.py](Demo/framework/cv_core/smoothing.py): temporal smoothing
- [Demo/framework/cv_core/instrument_6dof.py](Demo/framework/cv_core/instrument_6dof.py): solvePnP 6DoF estimator
- [Demo/framework/cv_core/hybrid_fusion.py](Demo/framework/cv_core/hybrid_fusion.py): confidence-weighted predict/update + constraints
- [Demo/framework/instruments/base.py](Demo/framework/instruments/base.py): plugin interface
- [Demo/framework/instruments/violin.py](Demo/framework/instruments/violin.py): violin plugin
- [Demo/framework/network/udp_broadcaster.py](Demo/framework/network/udp_broadcaster.py): UDP transport

## Why UDP

- Matches your existing Unity receiver approach.
- Lower overhead for local real-time streams.
- No connection lifecycle complexity.
- Integrates directly with [UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs](UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs).

## Install

```bash
pip install -r requirements.txt
```

## Run

Violin interpretation mode:

```bash
python Demo/run_realtime_framework.py --instrument violin --show-cv
```

If you want no instrument behavior at all, use:

```bash
python Demo/run_realtime_framework.py --instrument none --show-cv
```

This is webcam-only pose interpretation, not physical instrument detection.
The violin mode infers playing state from your body and hands.
If you want true markerless instrument detection, the next step is a trained detector model.

Optional intrinsics (recommended):

```bash
python Demo/run_realtime_framework.py --instrument violin --fx 1100 --fy 1100 --cx 640 --cy 360 --show-cv
```

You can still run the root launcher (compatibility wrapper):

```bash
python run_realtime_framework.py --instrument none --show-cv
```

## Unity Integration

Your existing [UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs](UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs) and [UnityProject/Assets/_Project/Scripts/AvatarController.cs](UnityProject/Assets/_Project/Scripts/AvatarController.cs) remain the primary path.

UDP payload format:

- JSON packet per frame
  - type: `hybrid_state_v2`
  - human joints: `{position, rotation(quat), confidence}`
  - instrument: `{position, rotation(quat), confidence}`
  - stable contact errors

The Unity receiver in [UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs](UnityProject/Assets/_Project/Scripts/MediapipeUDP.cs) parses `hybrid_state_v2` packets directly.

## Violin PnP Keypoint Calibration (Unity -> Python)

Use the Unity editor to author accurate 3D keypoints directly on your scaled violin model.

1. In Unity, select your violin root object and add `ViolinKeypointRig`.

1. To auto-generate outline/fingerboard/string helper points, click `Generate Supplementary Template`.

1. Move the generated driver markers in Scene view.

1. Mirrored left-side points are shown as gizmos only (they are not created as scene objects).

1. Exporter mirrors missing left-side points from right-side drivers and derives `center`, `neck_end`, `body_end`, `chin_anchor` from supplementary markers when possible.

1. Optional drawing-only markers (not used by PnP): `string_G_bridge_side`, `string_G_fingerboard_end` (and the same pattern for D/A/E), `outline_01_bottom_center`, `outline_02_bottom_right_corner`, ..., `fingerboard_01_bridge_right_side`, `fingerboard_02_nut_right_side`, ..., `bow_contact`, or any custom key name.

1. The supplementary template creates exactly these keys:
  `outline_01_bottom_center, outline_02_bottom_right_corner, outline_03_top_right_corner, outline_04_upper_middle_body_end` (outline drivers),
  `fingerboard_01_bridge_right_side, fingerboard_02_nut_right_side` (fingerboard drivers),
  `string_G_bridge_side,string_G_fingerboard_end,string_D_bridge_side,string_D_fingerboard_end,string_A_bridge_side,string_A_fingerboard_end,string_E_bridge_side,string_E_fingerboard_end` (2 points per string).

1. Click `Export Keypoints JSON`.

By default, export writes to `../Demo/config/instrument_profiles.unity.json` from Unity project root.

Run Python with that file:

```bash
python Demo/run_realtime_framework.py --instrument violin --calibration-file Demo/config/instrument_profiles.unity.json --show-cv
```

You can also copy the `profiles.violin.pnp_keypoints` block into [Demo/config/instrument_profiles.json](Demo/config/instrument_profiles.json).

`profiles.violin.geometry` is optional and controls non-PnP drawing geometry.

## Extending Instruments

To add a new instrument, implement `InstrumentModule.process(features)` in [Demo/framework/instruments/base.py](Demo/framework/instruments/base.py) and register it in [Demo/run_realtime_framework.py](Demo/run_realtime_framework.py).
