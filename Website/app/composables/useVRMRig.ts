import * as THREE from "three"
import { VRM, VRMHumanBoneName } from "@pixiv/three-vrm"
import { type HolisticResults, type LandmarkPoint, HandLandmark, PoseLandmark, getHandLandmark, getPoseLandmark } from "@/utils/landmarks"

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
	const smoothFactor = options.smoothFactor ?? 15
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
		const thumbAxis = isLeftAvatarHand ? new THREE.Vector3(-1, 0, 1).normalize() : new THREE.Vector3(1, 0, 1).normalize()
		// const fingerAxis = isLeftAvatarHand ? AXIS.xNegative : AXIS.xPositive
		const fingerAxis = isLeftAvatarHand ? AXIS.xPositive : AXIS.xNegative

		// applyDirection(isLeftAvatarHand ? "LeftThumbMetacarpal" : "RightThumbMetacarpal", thumbAxis, vectorBetween(handLandmarks, HandLandmark.ThumbCMC, HandLandmark.ThumbMCP), lerp)
		// applyDirection(isLeftAvatarHand ? "LeftThumbProximal" : "RightThumbProximal", thumbAxis, vectorBetween(handLandmarks, HandLandmark.ThumbMCP, HandLandmark.ThumbIP), lerp)
		// applyDirection(isLeftAvatarHand ? "LeftThumbDistal" : "RightThumbDistal", thumbAxis, vectorBetween(handLandmarks, HandLandmark.ThumbIP, HandLandmark.ThumbTIP), lerp)

		applyDirection(isLeftAvatarHand ? "LeftIndexProximal" : "RightIndexProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.IndexFingerMCP, HandLandmark.IndexFingerPIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftIndexIntermediate" : "RightIndexIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.IndexFingerPIP, HandLandmark.IndexFingerDIP), lerp)
		applyDirection(isLeftAvatarHand ? "LeftIndexDistal" : "RightIndexDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.IndexFingerDIP, HandLandmark.IndexFingerTIP), lerp)

		// applyDirection(isLeftAvatarHand ? "LeftMiddleProximal" : "RightMiddleProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.MiddleFingerMCP, HandLandmark.MiddleFingerPIP), lerp)
		// applyDirection(
		// 	isLeftAvatarHand ? "LeftMiddleIntermediate" : "RightMiddleIntermediate",
		// 	fingerAxis,
		// 	vectorBetween(handLandmarks, HandLandmark.MiddleFingerPIP, HandLandmark.MiddleFingerDIP),
		// 	lerp
		// )
		// applyDirection(isLeftAvatarHand ? "LeftMiddleDistal" : "RightMiddleDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.MiddleFingerDIP, HandLandmark.MiddleFingerTIP), lerp)

		// applyDirection(isLeftAvatarHand ? "LeftRingProximal" : "RightRingProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.RingFingerMCP, HandLandmark.RingFingerPIP), lerp)
		// applyDirection(isLeftAvatarHand ? "LeftRingIntermediate" : "RightRingIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.RingFingerPIP, HandLandmark.RingFingerDIP), lerp)
		// applyDirection(isLeftAvatarHand ? "LeftRingDistal" : "RightRingDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.RingFingerDIP, HandLandmark.RingFingerTIP), lerp)

		// applyDirection(isLeftAvatarHand ? "LeftLittleProximal" : "RightLittleProximal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.PinkyMCP, HandLandmark.PinkyPIP), lerp)
		// applyDirection(isLeftAvatarHand ? "LeftLittleIntermediate" : "RightLittleIntermediate", fingerAxis, vectorBetween(handLandmarks, HandLandmark.PinkyPIP, HandLandmark.PinkyDIP), lerp)
		// applyDirection(isLeftAvatarHand ? "LeftLittleDistal" : "RightLittleDistal", fingerAxis, vectorBetween(handLandmarks, HandLandmark.PinkyDIP, HandLandmark.PinkyTIP), lerp)
	}

	const applyHands = (leftHandLandmarks: LandmarkPoint[] | null | undefined, rightHandLandmarks: LandmarkPoint[] | null | undefined) => {
		applyHandChain(rightHandLandmarks, false)
		applyHandChain(leftHandLandmarks, true)
	}

	const update = (results: HolisticResults) => {
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
