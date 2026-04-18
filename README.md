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
- [Demo/framework/instruments/flute.py](Demo/framework/instruments/flute.py): flute plugin
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

Flute interpretation mode:

```bash
python Demo/run_realtime_framework.py --instrument flute --show-cv
```

If you want no instrument behavior at all, use:

```bash
python Demo/run_realtime_framework.py --instrument none --show-cv
```

This is webcam-only pose interpretation, not physical instrument detection.
The violin and flute modes infer playing state from your body and hands.
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

## Extending Instruments

To add a new instrument, implement `InstrumentModule.process(features)` in [Demo/framework/instruments/base.py](Demo/framework/instruments/base.py) and register it in [Demo/run_realtime_framework.py](Demo/run_realtime_framework.py).
