import * as THREE from "three"
import { VRM, VRMHumanBoneName } from "@pixiv/three-vrm"
import { type HolisticResults, type LandmarkPoint, HandLandmark, PoseLandmark, getHandLandmark, getPoseLandmark } from "@/utils/landmarks"
import { normalizeHolisticResults } from "@/utils/landmarkTransforms"

type RigOptions = {
	smoothFactor?: number
	debugMode?: boolean
	showBoneAxes?: boolean
}

const AXIS = {
	xPositive: new THREE.Vector3(1, 0, 0),
	xNegative: new THREE.Vector3(-1, 0, 0),
	yPositive: new THREE.Vector3(0, 1, 0),
	yNegative: new THREE.Vector3(0, -1, 0),
	zPositive: new THREE.Vector3(0, 0, 1),
	zNegative: new THREE.Vector3(0, 0, -1),
}

export const useVRMRig = (vrm: VRM | null, options: RigOptions = {}) => {
	const smoothFactor = 100 // options.smoothFactor ?? 15
	// const debugMode = options.debugMode ?? false
	const debugMode = true
	let lastUpdateAt = performance.now()
	const axesHelpers: THREE.AxesHelper[] = []
	let axesInitialized = false

	const initializeBoneAxes = () => {
		if (axesInitialized || !vrm) return

		const bonesToVisualize: (keyof typeof VRMHumanBoneName)[] = [
			"Hips",
			"Spine",
			"Chest",
			"UpperChest",
			"Neck",
			"Head",
			"LeftShoulder",
			"LeftUpperArm",
			"LeftLowerArm",
			"LeftHand",
			"RightShoulder",
			"RightUpperArm",
			"RightLowerArm",
			"RightHand",
			"LeftUpperLeg",
			"LeftLowerLeg",
			"LeftFoot",
			"RightUpperLeg",
			"RightLowerLeg",
			"RightFoot",
		]

		bonesToVisualize.forEach((boneName) => {
			const bone = getBone(boneName)
			if (bone) {
				const helper = new THREE.AxesHelper(0.15)
				bone.add(helper)
				helper.visible = options.showBoneAxes ?? false
				axesHelpers.push(helper)
			}
		})

		axesInitialized = true
	}

	const setShowBoneAxes = (show: boolean) => {
		// Ensure axes are initialized before trying to show them
		if (!axesInitialized) {
			initializeBoneAxes()
		}
		axesHelpers.forEach((helper) => {
			helper.visible = show
		})
	}

	const getBone = (name: keyof typeof VRMHumanBoneName) => {
		return vrm?.humanoid.getNormalizedBoneNode(VRMHumanBoneName[name])
	}

	const axisCorrectionByBone = new Map<keyof typeof VRMHumanBoneName, THREE.Quaternion>()

	const resolveCorrectedLocalAxis = (name: keyof typeof VRMHumanBoneName, configuredAxisLocal: THREE.Vector3) => {
		const cachedCorrection = axisCorrectionByBone.get(name)
		if (cachedCorrection) {
			return configuredAxisLocal.clone().normalize().applyQuaternion(cachedCorrection).normalize()
		}

		const bone = getBone(name)
		if (!bone) return configuredAxisLocal.clone().normalize()

		const child = bone.children.find((node) => node.position.lengthSq() > 1e-8) ?? null
		if (!child || child.position.lengthSq() < 1e-8) {
			axisCorrectionByBone.set(name, new THREE.Quaternion())
			return configuredAxisLocal.clone().normalize()
		}

		const configured = configuredAxisLocal.clone().normalize()
		const childDirectionLocal = child.position.clone().normalize()
		const correction = new THREE.Quaternion().setFromUnitVectors(configured, childDirectionLocal)

		axisCorrectionByBone.set(name, correction)
		return configured.applyQuaternion(correction).normalize()
	}

	const drawDebugLine = (start: THREE.Vector3, direction: THREE.Vector3, color: number, length = 0.2, ttlMs = 100) => {
		if (!debugMode || direction.lengthSq() < 1e-6) return

		const scene = getBone("Hips")?.parent ?? null
		if (!scene) return

		const end = start.clone().add(direction.clone().normalize().multiplyScalar(length))
		const geometry = new THREE.BufferGeometry().setFromPoints([start.clone(), end])
		const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95 })
		const line = new THREE.Line(geometry, material)

		scene.add(line)
		setTimeout(() => {
			scene.remove(line)
			geometry.dispose()
			material.dispose()
		}, ttlMs)
	}

	const midpoint = (a: LandmarkPoint, b: LandmarkPoint) => {
		return new THREE.Vector3((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, ((a.z ?? 0) + (b.z ?? 0)) * 0.5)
	}

	const vectorBetween = (landmarks: LandmarkPoint[] | null | undefined, fromIndex: number, toIndex: number) => {
		const from = landmarks?.[fromIndex] ?? null
		const to = landmarks?.[toIndex] ?? null

		if (!from || !to) return null
		return new THREE.Vector3((to.x ?? 0) - (from.x ?? 0), (to.y ?? 0) - (from.y ?? 0), (to.z ?? 0) - (from.z ?? 0))
	}

	const nextLerp = () => {
		const now = performance.now()
		const deltaSeconds = Math.max((now - lastUpdateAt) / 1000, 1 / 120)
		lastUpdateAt = now
		return Math.min(1, deltaSeconds * smoothFactor)
	}

	const applyWorldRotation = (name: keyof typeof VRMHumanBoneName, targetWorldRotation: THREE.Quaternion, lerp: number) => {
		const bone = getBone(name)
		if (!bone) return

		const parentInverseWorldRotation = new THREE.Quaternion()
		if (bone.parent) {
			bone.parent.getWorldQuaternion(parentInverseWorldRotation).invert()
		}

		const targetLocalRotation = parentInverseWorldRotation.multiply(targetWorldRotation)
		bone.quaternion.slerp(targetLocalRotation, lerp)
	}

	const applyOrientation = (
		name: keyof typeof VRMHumanBoneName,
		boneAxisForwardLocal: THREE.Vector3,
		boneAxisUpLocal: THREE.Vector3,
		targetForwardWorld: THREE.Vector3 | null,
		targetUpWorld: THREE.Vector3 | null,
		lerp: number
	) => {
		const bone = getBone(name)
		if (!bone || !targetForwardWorld || !targetUpWorld || targetForwardWorld.lengthSq() < 1e-6 || targetUpWorld.lengthSq() < 1e-6) return

		const fwdTarget = targetForwardWorld.clone().normalize()
		const upTarget = targetUpWorld.clone().normalize()

		const fwdLocal = resolveCorrectedLocalAxis(name, boneAxisForwardLocal)
		const upLocal = resolveCorrectedLocalAxis(name, boneAxisUpLocal)

		// 1. Align Forward
		const currentWorldQuat = new THREE.Quaternion()
		bone.getWorldQuaternion(currentWorldQuat)

		const fwdWorld = fwdLocal.clone().applyQuaternion(currentWorldQuat).normalize()
		const alignFwd = new THREE.Quaternion().setFromUnitVectors(fwdWorld, fwdTarget)
		const firstAlignedQuat = alignFwd.clone().multiply(currentWorldQuat)

		// 2. Align Up (roll around the matched forward axis)
		const currentUpWorld = upLocal.clone().applyQuaternion(firstAlignedQuat).normalize()
		// project upTarget onto the plane orthogonal to fwdTarget to isolate the roll
		const projectedUpTarget = upTarget.clone().projectOnPlane(fwdTarget).normalize()
		const projectedCurrentUp = currentUpWorld.clone().projectOnPlane(fwdTarget).normalize()
		
		const alignUp = new THREE.Quaternion().setFromUnitVectors(projectedCurrentUp, projectedUpTarget)
		const desiredWorldQuat = alignUp.clone().multiply(firstAlignedQuat)

		// convert to local
		const parentWorldQuaternion = new THREE.Quaternion()
		if (bone.parent) {
			bone.parent.getWorldQuaternion(parentWorldQuaternion)
		}

		const localTargetRotation = parentWorldQuaternion.clone().invert().multiply(desiredWorldQuat)
		bone.quaternion.slerp(localTargetRotation, lerp)
	}

	const applyDirection = (name: keyof typeof VRMHumanBoneName, boneAxisLocalOrient: THREE.Vector3, targetDirectionWorld: THREE.Vector3 | null, lerp: number) => {
		const bone = getBone(name)
		if (!bone || !targetDirectionWorld || targetDirectionWorld.lengthSq() < 1e-6) return

		const targetDir = targetDirectionWorld.clone().normalize()
		const boneAxisLocal = resolveCorrectedLocalAxis(name, boneAxisLocalOrient)

		// current bone world rotation
		const currentWorldQuat = new THREE.Quaternion()
		bone.getWorldQuaternion(currentWorldQuat)

		// compute current axis in world
		const axisWorld = boneAxisLocal.clone().applyQuaternion(currentWorldQuat).normalize()

		// if (debugMode) {
		// 	const boneWorldPosition = new THREE.Vector3()
		// 	bone.getWorldPosition(boneWorldPosition)

		// 	// green = target direction, red = axis from configured bone axis, cyan = current computed axis
		// 	drawDebugLine(boneWorldPosition, targetDir, 0x00ff66, 1)
		// 	drawDebugLine(boneWorldPosition, boneAxisLocal.clone().applyQuaternion(currentWorldQuat), 0xff5555, 1)
		// 	drawDebugLine(boneWorldPosition, axisWorld, 0x33c3ff, 1)
		// }

		// delta to align axis → target
		const deltaRotation = new THREE.Quaternion().setFromUnitVectors(axisWorld, targetDir)

		// apply in world space
		const desiredWorldQuat = deltaRotation.clone().multiply(currentWorldQuat)

		// convert to local
		const parentWorldQuaternion = new THREE.Quaternion()
		if (bone.parent) {
			bone.parent.getWorldQuaternion(parentWorldQuaternion)
		}

		const localTargetRotation = parentWorldQuaternion.clone().invert().multiply(desiredWorldQuat)

		bone.quaternion.slerp(localTargetRotation, lerp)
	}

	const applyTorso = (poseLandmarks: LandmarkPoint[] | null | undefined) => {
		const leftHip = getPoseLandmark(poseLandmarks, PoseLandmark.LeftHip)
		const rightHip = getPoseLandmark(poseLandmarks, PoseLandmark.RightHip)
		const leftShoulder = getPoseLandmark(poseLandmarks, PoseLandmark.LeftShoulder)
		const rightShoulder = getPoseLandmark(poseLandmarks, PoseLandmark.RightShoulder)

		if (!leftHip || !rightHip || !leftShoulder || !rightShoulder) return

		const hipCenter = midpoint(leftHip, rightHip)
		const shoulderCenter = midpoint(leftShoulder, rightShoulder)
		const up = shoulderCenter.clone().sub(hipCenter)
		const right = new THREE.Vector3(rightHip.x - leftHip.x, rightHip.y - leftHip.y, (rightHip.z ?? 0) - (leftHip.z ?? 0))

		if (up.lengthSq() < 0.000001 || right.lengthSq() < 0.000001) return

		up.normalize()
		right.normalize()
		const forward = new THREE.Vector3().crossVectors(right, up).multiplyScalar(-1).normalize()
		const targetRotation = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(right, up, forward))
		const lerp = nextLerp()

		applyWorldRotation("Hips", targetRotation, lerp)
		applyWorldRotation("Spine", targetRotation, lerp * 0.85)
		applyWorldRotation("Chest", targetRotation, lerp * 0.9)
		applyWorldRotation("UpperChest", targetRotation, lerp)

		if (debugMode) {
			void hipCenter
			void shoulderCenter
		}
	}

	const applyArms = (poseLandmarks: LandmarkPoint[] | null | undefined) => {
		const lerp = nextLerp()

		applyDirection("LeftUpperArm", AXIS.xNegative, vectorBetween(poseLandmarks, PoseLandmark.LeftShoulder, PoseLandmark.LeftElbow), lerp)
		applyDirection("LeftLowerArm", AXIS.xNegative, vectorBetween(poseLandmarks, PoseLandmark.LeftElbow, PoseLandmark.LeftWrist), lerp)
		applyDirection("LeftHand", AXIS.xNegative, vectorBetween(poseLandmarks, PoseLandmark.LeftWrist, PoseLandmark.LeftIndex), lerp)

		applyDirection("RightUpperArm", AXIS.xPositive, vectorBetween(poseLandmarks, PoseLandmark.RightShoulder, PoseLandmark.RightElbow), lerp)
		applyDirection("RightLowerArm", AXIS.xPositive, vectorBetween(poseLandmarks, PoseLandmark.RightElbow, PoseLandmark.RightWrist), lerp)
		applyDirection("RightHand", AXIS.xPositive, vectorBetween(poseLandmarks, PoseLandmark.RightWrist, PoseLandmark.RightIndex), lerp)
	}

	const applyLegs = (poseLandmarks: LandmarkPoint[] | null | undefined) => {
		const lerp = nextLerp()

		applyDirection("LeftUpperLeg", AXIS.yPositive, vectorBetween(poseLandmarks, PoseLandmark.LeftHip, PoseLandmark.LeftKnee), lerp)
		applyDirection("LeftLowerLeg", AXIS.yPositive, vectorBetween(poseLandmarks, PoseLandmark.LeftKnee, PoseLandmark.LeftAnkle), lerp)
		applyDirection("LeftFoot", AXIS.zNegative, vectorBetween(poseLandmarks, PoseLandmark.LeftAnkle, PoseLandmark.LeftFootIndex), lerp)

		applyDirection("RightUpperLeg", AXIS.yPositive, vectorBetween(poseLandmarks, PoseLandmark.RightHip, PoseLandmark.RightKnee), lerp)
		applyDirection("RightLowerLeg", AXIS.yPositive, vectorBetween(poseLandmarks, PoseLandmark.RightKnee, PoseLandmark.RightAnkle), lerp)
		applyDirection("RightFoot", AXIS.zNegative, vectorBetween(poseLandmarks, PoseLandmark.RightAnkle, PoseLandmark.RightFootIndex), lerp)
	}

	const applyHandChain = (handLandmarks: LandmarkPoint[] | null | undefined, isLeftAvatarHand: boolean) => {
		if (!handLandmarks) return

		const lerp = nextLerp()

		// 1. Orient the Wrist (fixes roll/twist for the entire hand so fingers don't break)
		const wrist = handLandmarks[HandLandmark.Wrist];
		const indexMCP = handLandmarks[HandLandmark.IndexFingerMCP];
		const pinkyMCP = handLandmarks[HandLandmark.PinkyMCP];
		const middleMCP = handLandmarks[HandLandmark.MiddleFingerMCP];
		
		if (wrist && indexMCP && pinkyMCP && middleMCP) {
			const posWrist = new THREE.Vector3(wrist.x, wrist.y, wrist.z ?? 0);
			const posIndex = new THREE.Vector3(indexMCP.x, indexMCP.y, indexMCP.z ?? 0);
			const posPinky = new THREE.Vector3(pinkyMCP.x, pinkyMCP.y, pinkyMCP.z ?? 0);
			const posMiddle = new THREE.Vector3(middleMCP.x, middleMCP.y, middleMCP.z ?? 0);

			const targetForward = new THREE.Vector3().subVectors(posMiddle, posWrist).normalize();
			
			// Right knuckle cross product calculation
			const crossKnuckles = isLeftAvatarHand 
				? new THREE.Vector3().subVectors(posIndex, posPinky).normalize() // Left hand
				: new THREE.Vector3().subVectors(posPinky, posIndex).normalize(); // Right hand
				
			const targetUp = new THREE.Vector3().crossVectors(crossKnuckles, targetForward).normalize();

			// Apply baseline pitch offset to neutralize VRM wrist extension
			const wristPitchOffset = 0.35;
			targetForward.applyAxisAngle(crossKnuckles, wristPitchOffset);
			targetUp.applyAxisAngle(crossKnuckles, wristPitchOffset);

			const forwardAxis = isLeftAvatarHand ? AXIS.xNegative : AXIS.xPositive;
			// Roll axis varies, but Y+ is standard for back-of-hand.
			const upAxis = AXIS.yPositive; 

			applyOrientation(isLeftAvatarHand ? "LeftHand" : "RightHand", forwardAxis, upAxis, targetForward, targetUp, lerp);
		}

		// 2. Orient the Fingers
		// If the thumb is backwards, its local Z or Y axis mapping is inverted compared to the fingers.
		// Changing the left thumb axis Z from 1 to -1 flattens/fixes the backward bending loop. (Tune this if it bends too far down!)
		const thumbAxis = isLeftAvatarHand ? new THREE.Vector3(-1, 0, -1).normalize() : new THREE.Vector3(1, 0, 1).normalize()
		const fingerAxis = isLeftAvatarHand ? AXIS.xNegative : AXIS.xPositive

		// Thumb
		applyDirection(isLeftAvatarHand ? "LeftThumbMetacarpal" : "RightThumbMetacarpal", thumbAxis, vectorBetween(handLandmarks, HandLandmark.ThumbCMC, HandLandmark.ThumbMCP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftThumbProximal" : "RightThumbProximal", thumbAxis, vectorBetween(handLandmarks, HandLandmark.ThumbMCP, HandLandmark.ThumbIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftThumbDistal" : "RightThumbDistal", thumbAxis, vectorBetween(handLandmarks, HandLandmark.ThumbIP, HandLandmark.ThumbTIP), lerp)

		// Index finger
		applyDirection(isLeftAvatarHand ? "LeftIndexProximal" : "RightIndexProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.IndexFingerMCP, HandLandmark.IndexFingerPIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftIndexIntermediate" : "RightIndexIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.IndexFingerPIP, HandLandmark.IndexFingerDIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftIndexDistal" : "RightIndexDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.IndexFingerDIP, HandLandmark.IndexFingerTIP), lerp)

		// Middle finger
		applyDirection(isLeftAvatarHand ? "LeftMiddleProximal" : "RightMiddleProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.MiddleFingerMCP, HandLandmark.MiddleFingerPIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftMiddleIntermediate" : "RightMiddleIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.MiddleFingerPIP, HandLandmark.MiddleFingerDIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftMiddleDistal" : "RightMiddleDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.MiddleFingerDIP, HandLandmark.MiddleFingerTIP), lerp)

		// Ring finger
		applyDirection(isLeftAvatarHand ? "LeftRingProximal" : "RightRingProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.RingFingerMCP, HandLandmark.RingFingerPIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftRingIntermediate" : "RightRingIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.RingFingerPIP, HandLandmark.RingFingerDIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftRingDistal" : "RightRingDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.RingFingerDIP, HandLandmark.RingFingerTIP), lerp)

		// Pinky
		applyDirection(isLeftAvatarHand ? "LeftLittleProximal" : "RightLittleProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.PinkyMCP, HandLandmark.PinkyPIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftLittleIntermediate" : "RightLittleIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.PinkyPIP, HandLandmark.PinkyDIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftLittleDistal" : "RightLittleDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.PinkyDIP, HandLandmark.PinkyTIP), lerp)
	}

	const applyRightHandBowGrip = (handLandmarks: LandmarkPoint[] | null | undefined, isLeftAvatarHand: boolean) => {
		const setBoneRotation = (boneName: keyof typeof VRMHumanBoneName, x: number, y: number, z: number) => {
			const bone = getBone(boneName)
			if (bone) {
                if (!boneName.includes("RightThumb")) {
                    z -= 1.5
                    y -= 0.5
                }
				const targetQuat = new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z))
				const lerp = nextLerp()
				bone.quaternion.slerp(targetQuat, lerp)
			}
		}

		// Hard-coded bow grip positions (in radians)
		// Assuming bending primarily occurs around the Z axis, but this can be tweaked.
		// Values reflect a classic string bow grip:
		
		// Thumb: curved under the stick
		setBoneRotation("RightThumbMetacarpal", -1, 0, 0)
		setBoneRotation("RightThumbProximal", -1.5, 0, 0)
		setBoneRotation("RightThumbDistal", -1.5, 0, 0)

		//Index: resting on the pad, somewhat curled
		setBoneRotation("RightIndexProximal", 0, 0, 0.5)
		setBoneRotation("RightIndexIntermediate", 0, 0, 0.4)
		setBoneRotation("RightIndexDistal", 0, 0, 0.2)

		// Middle: draped over the frog / stick
		setBoneRotation("RightMiddleProximal", 0, 0, 0.5)
		setBoneRotation("RightMiddleIntermediate", 0, 0, 0.4)
		setBoneRotation("RightMiddleDistal", 0, 0, 0.2)

		// Ring: draped next to middle
		setBoneRotation("RightRingProximal", 0, 0, 0.5)
		setBoneRotation("RightRingIntermediate", 0, 0, 0.4)
		setBoneRotation("RightRingDistal", 0, 0, 0.2)

		// Pinky: curved and resting on top of the stick
		setBoneRotation("RightLittleProximal", 0, -0.1, 0.5)
		setBoneRotation("RightLittleIntermediate", 0, 0, 0.4)
		setBoneRotation("RightLittleDistal", 0, 0, 0.2)

		if (!handLandmarks) return;

		// Compute forward and up vectors from landmarks for wrist control
		const wrist = handLandmarks[HandLandmark.Wrist];
		const indexMCP = handLandmarks[HandLandmark.IndexFingerMCP];
		const pinkyMCP = handLandmarks[HandLandmark.PinkyMCP];
		const middleMCP = handLandmarks[HandLandmark.MiddleFingerMCP];
		
		if (!wrist || !indexMCP || !pinkyMCP || !middleMCP) return;

		const posWrist = new THREE.Vector3(wrist.x, wrist.y, wrist.z ?? 0);
		const posIndex = new THREE.Vector3(indexMCP.x, indexMCP.y, indexMCP.z ?? 0);
		const posPinky = new THREE.Vector3(pinkyMCP.x, pinkyMCP.y, pinkyMCP.z ?? 0);
		const posMiddle = new THREE.Vector3(middleMCP.x, middleMCP.y, middleMCP.z ?? 0);

		// Forward: Wrist to Middle Finger
		const targetForward = new THREE.Vector3().subVectors(posMiddle, posWrist).normalize();
		// Knuckles cross: Index to Pinky
		const crossKnuckles = new THREE.Vector3().subVectors(posPinky, posIndex).normalize();
		// Up: Back of hand normal
		const targetUp = new THREE.Vector3().crossVectors(crossKnuckles, targetForward).normalize();

		// The natural wrist-to-MCP vector often appears bent slightly backwards (extended) 
		// on typical VRM models compared to the visual forearm axis. 
		// Tweak this pitch offset (in radians) to correct the baseline flexion/extension.
		// Positive values flex the wrist inward (towards the palm). Negative extends it outward.
		const wristPitchOffset = 0.75; // roughly 20 degrees
		targetForward.applyAxisAngle(crossKnuckles, wristPitchOffset);
		targetUp.applyAxisAngle(crossKnuckles, wristPitchOffset);

		// Right hand VRM typical axes:
		// Forward points roughly +X (down the arm)
		// Up (back of hand) points roughly +Y or +Z depending on export. 
		// We'll assume Y is up and standard X is forward.
		const lerp = nextLerp();
		applyOrientation("RightHand", AXIS.xPositive, AXIS.yPositive, targetForward, targetUp, lerp);
	}

	const applyHands = (leftHandLandmarks: LandmarkPoint[] | null | undefined, rightHandLandmarks: LandmarkPoint[] | null | undefined) => {
		applyRightHandBowGrip(rightHandLandmarks, false)
		applyHandChain(leftHandLandmarks, true)
	}

	const update = (rawResults: HolisticResults) => {
		const results = normalizeHolisticResults(rawResults)
		// Initialize axes on first update (they're added but hidden/shown via setShowBoneAxes)
		if (!axesInitialized) {
			initializeBoneAxes()
		}

		if (results.poseLandmarks) {
			// applyTorso(results.poseLandmarks)
			applyArms(results.poseLandmarks)
			// applyLegs(results.poseLandmarks)
		}

		applyHands(results.leftHandLandmarks ?? null, results.rightHandLandmarks ?? null)
		vrm?.update(1 / 60)
	}

	return {
		update,
		applyTorso,
		applyArms,
		applyLegs,
		applyHands,
		getBone,
		setShowBoneAxes,
	}
}
