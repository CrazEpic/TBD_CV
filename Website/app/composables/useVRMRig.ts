import * as THREE from "three"
import { VRM, VRMHumanBoneName } from "@pixiv/three-vrm"
import { type HolisticResults, type LandmarkPoint, HandLandmark, PoseLandmark, getHandLandmark, getPoseLandmark } from "@/utils/landmarks"
import { normalizeHolisticResults } from "@/utils/landmarkTransforms"

type RigOptions = {
	smoothFactor?: number
	debugMode?: boolean
	showBoneAxes?: boolean
}

export type LeftHandFinger = "index" | "middle" | "ring" | "pinky"

const LEFT_DISTAL_BONE_BY_FINGER: Record<LeftHandFinger, keyof typeof VRMHumanBoneName> = {
	index: "LeftIndexDistal",
	middle: "LeftMiddleDistal",
	ring: "LeftRingDistal",
	pinky: "LeftLittleDistal",
}

const EPSILON = 1e-5

type BoneName = keyof typeof VRMHumanBoneName

type FingerDefinition = {
	mcp: HandLandmark
	pip: HandLandmark
	dip: HandLandmark
	tip: HandLandmark
	bones: [BoneName, BoneName, BoneName]
}

const FINGER_DEFINITIONS: Record<"index" | "middle" | "ring" | "pinky", FingerDefinition> = {
	index: {
		mcp: HandLandmark.IndexFingerMCP,
		pip: HandLandmark.IndexFingerPIP,
		dip: HandLandmark.IndexFingerDIP,
		tip: HandLandmark.IndexFingerTIP,
		bones: ["LeftIndexProximal", "LeftIndexIntermediate", "LeftIndexDistal"],
	},
	middle: {
		mcp: HandLandmark.MiddleFingerMCP,
		pip: HandLandmark.MiddleFingerPIP,
		dip: HandLandmark.MiddleFingerDIP,
		tip: HandLandmark.MiddleFingerTIP,
		bones: ["LeftMiddleProximal", "LeftMiddleIntermediate", "LeftMiddleDistal"],
	},
	ring: {
		mcp: HandLandmark.RingFingerMCP,
		pip: HandLandmark.RingFingerPIP,
		dip: HandLandmark.RingFingerDIP,
		tip: HandLandmark.RingFingerTIP,
		bones: ["LeftRingProximal", "LeftRingIntermediate", "LeftRingDistal"],
	},
	pinky: {
		mcp: HandLandmark.PinkyMCP,
		pip: HandLandmark.PinkyPIP,
		dip: HandLandmark.PinkyDIP,
		tip: HandLandmark.PinkyTIP,
		bones: ["LeftLittleProximal", "LeftLittleIntermediate", "LeftLittleDistal"],
	},
}

const RIGHT_FINGER_BONE_BY_LEFT_BONE: Partial<Record<BoneName, BoneName>> = {
	LeftHand: "RightHand",
	LeftIndexProximal: "RightIndexProximal",
	LeftIndexIntermediate: "RightIndexIntermediate",
	LeftIndexDistal: "RightIndexDistal",
	LeftMiddleProximal: "RightMiddleProximal",
	LeftMiddleIntermediate: "RightMiddleIntermediate",
	LeftMiddleDistal: "RightMiddleDistal",
	LeftRingProximal: "RightRingProximal",
	LeftRingIntermediate: "RightRingIntermediate",
	LeftRingDistal: "RightRingDistal",
	LeftLittleProximal: "RightLittleProximal",
	LeftLittleIntermediate: "RightLittleIntermediate",
	LeftLittleDistal: "RightLittleDistal",
}

export const useVRMRig = (vrm: VRM | null, options: RigOptions = {}) => {
	const smoothFactor = options.smoothFactor ?? 15
	const debugMode = options.debugMode ?? false
	let lastUpdateAt = performance.now()
	const axesHelpers: THREE.AxesHelper[] = []
	let axesInitialized = false

	const temp = {
		a: new THREE.Vector3(),
		b: new THREE.Vector3(),
		c: new THREE.Vector3(),
		d: new THREE.Vector3(),
		q1: new THREE.Quaternion(),
		q2: new THREE.Quaternion(),
		m1: new THREE.Matrix4(),
		m2: new THREE.Matrix4(),
	}

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

	const resolveBoneName = (leftBone: BoneName, isRightHand: boolean) => {
		if (!isRightHand) return leftBone
		return RIGHT_FINGER_BONE_BY_LEFT_BONE[leftBone] ?? leftBone
	}

	const getAlpha = () => {
		const now = performance.now()
		const dt = Math.max(1 / 120, (now - lastUpdateAt) / 1000)
		lastUpdateAt = now
		if (smoothFactor <= 0) return 1
		return 1 - Math.exp(-smoothFactor * dt)
	}

	const getLandmarkVector = (landmark: LandmarkPoint | null | undefined) => {
		if (!landmark) return null
		if (!Number.isFinite(landmark.x) || !Number.isFinite(landmark.y)) return null
		const z = landmark.z ?? 0
		if (!Number.isFinite(z)) return null
		return new THREE.Vector3(landmark.x, landmark.y, z)
	}

	const getDirection = (from: THREE.Vector3 | null, to: THREE.Vector3 | null) => {
		if (!from || !to) return null
		const dir = temp.a.copy(to).sub(from)
		if (dir.lengthSq() < EPSILON) return null
		return dir.normalize().clone()
	}

	const getParentWorldQuaternion = (bone: THREE.Object3D) => {
		if (!bone.parent) return temp.q1.identity().clone()
		bone.parent.getWorldQuaternion(temp.q1)
		return temp.q1.clone()
	}

	const applyBoneFromDirection = (boneName: BoneName, childBoneName: BoneName, targetWorldDir: THREE.Vector3, alpha: number) => {
		const bone = getBone(boneName)
		const child = getBone(childBoneName)
		if (!bone || !child) return

		const restLocalDir = temp.b.copy(child.position)
		if (restLocalDir.lengthSq() < EPSILON) return
		restLocalDir.normalize()

		const parentWorldQ = getParentWorldQuaternion(bone)
		const targetLocalDir = temp.c.copy(targetWorldDir).applyQuaternion(parentWorldQ.invert()).normalize()

		const targetRotation = temp.q2.setFromUnitVectors(restLocalDir, targetLocalDir)
		bone.quaternion.slerp(targetRotation, alpha)
		bone.updateMatrixWorld(true)
	}

	const applyBoneBetweenPoints = (
		boneName: BoneName,
		childBoneName: BoneName,
		start: THREE.Vector3 | null,
		end: THREE.Vector3 | null,
		alpha: number,
	) => {
		const dir = getDirection(start, end)
		if (!dir) return
		applyBoneFromDirection(boneName, childBoneName, dir, alpha)
	}

	const buildPalmBasis = (wrist: THREE.Vector3, indexMcp: THREE.Vector3, middleMcp: THREE.Vector3, pinkyMcp: THREE.Vector3) => {
		const forward = temp.a.copy(middleMcp).sub(wrist).normalize()
		const across = temp.b.copy(pinkyMcp).sub(indexMcp).normalize()
		const normal = temp.c.crossVectors(across, forward)
		if (forward.lengthSq() < EPSILON || across.lengthSq() < EPSILON || normal.lengthSq() < EPSILON) return null
		normal.normalize()
		const right = temp.d.crossVectors(forward, normal).normalize()
		const basis = temp.m1.identity().makeBasis(right, forward, normal)
		return basis.clone()
	}

	const applyHandWristBasis = (
		handBoneName: BoneName,
		indexBoneName: BoneName,
		middleBoneName: BoneName,
		pinkyBoneName: BoneName,
		wrist: THREE.Vector3,
		indexMcp: THREE.Vector3,
		middleMcp: THREE.Vector3,
		pinkyMcp: THREE.Vector3,
		alpha: number,
	) => {
		const handBone = getBone(handBoneName)
		const indexBone = getBone(indexBoneName)
		const middleBone = getBone(middleBoneName)
		const pinkyBone = getBone(pinkyBoneName)
		if (!handBone || !indexBone || !middleBone || !pinkyBone) return

		const targetBasisWorld = buildPalmBasis(wrist, indexMcp, middleMcp, pinkyMcp)
		if (!targetBasisWorld) return

		const parentWorldQ = getParentWorldQuaternion(handBone)
		const parentWorldM = temp.m2.identity().makeRotationFromQuaternion(parentWorldQ)
		const targetBasisLocal = targetBasisWorld.clone().premultiply(parentWorldM.clone().invert())

		const restForward = temp.a.copy(middleBone.position)
		const restAcross = temp.b.copy(pinkyBone.position).sub(indexBone.position)
		const restNormal = temp.c.crossVectors(restAcross, restForward)
		if (restForward.lengthSq() < EPSILON || restAcross.lengthSq() < EPSILON || restNormal.lengthSq() < EPSILON) return
		restForward.normalize()
		restAcross.normalize()
		restNormal.normalize()
		const restRight = temp.d.crossVectors(restForward, restNormal).normalize()

		const restBasis = temp.m1.identity().makeBasis(restRight, restForward, restNormal)
		const restQ = new THREE.Quaternion().setFromRotationMatrix(restBasis)
		const targetQ = new THREE.Quaternion().setFromRotationMatrix(targetBasisLocal)
		const localRotation = targetQ.multiply(restQ.invert())

		handBone.quaternion.slerp(localRotation, alpha)
		handBone.updateMatrixWorld(true)
	}

	const getCenter = (a: THREE.Vector3 | null, b: THREE.Vector3 | null) => {
		if (!a || !b) return null
		return a.clone().add(b).multiplyScalar(0.5)
	}

	const getScaledPoint = (origin: THREE.Vector3 | null, dir: THREE.Vector3 | null, scale: number) => {
		if (!origin || !dir) return null
		return origin.clone().add(dir.clone().multiplyScalar(scale))
	}

	const lerpPoints = (a: THREE.Vector3 | null, b: THREE.Vector3 | null, t: number) => {
		if (!a || !b) return null
		return a.clone().lerp(b, t)
	}

	const updatePoseRig = (poseLandmarks: LandmarkPoint[], alpha: number) => {
		const leftShoulder = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftShoulder))
		const rightShoulder = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightShoulder))
		const leftElbow = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftElbow))
		const rightElbow = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightElbow))
		const leftWrist = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftWrist))
		const rightWrist = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightWrist))

		const leftHip = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftHip))
		const rightHip = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightHip))
		// const leftKnee = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftKnee))
		// const rightKnee = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightKnee))
		// const leftAnkle = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftAnkle))
		// const rightAnkle = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightAnkle))

		// const leftFootIndex = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftFootIndex))
		// const rightFootIndex = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightFootIndex))
		// const leftHeel = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftHeel))
		// const rightHeel = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightHeel))

		const leftEar = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.LeftEar))
		const rightEar = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.RightEar))
		const nose = getLandmarkVector(getPoseLandmark(poseLandmarks, PoseLandmark.Nose))

		const hipsCenter = getCenter(leftHip, rightHip)
		const shouldersCenter = getCenter(leftShoulder, rightShoulder)
		const earsCenter = getCenter(leftEar, rightEar) ?? nose

		const spineDir = getDirection(hipsCenter, shouldersCenter)

		// Use actual segment interpolation (not normalized direction scaling) so right shoulder
		// inside anchor remains on the right side even when shoulder width is small.
		const leftShoulderInner = lerpPoints(leftShoulder, rightShoulder, 1 / 3)
		const rightShoulderInner = lerpPoints(leftShoulder, rightShoulder, 2 / 3)

		const neck = shouldersCenter && spineDir && leftShoulder && rightShoulder
			? shouldersCenter.clone().add(spineDir.clone().multiplyScalar(leftShoulder.distanceTo(rightShoulder) * 0.12))
			: shouldersCenter
		const head = neck && earsCenter ? neck.clone().lerp(earsCenter, 0.65) : earsCenter

		if (hipsCenter && leftHip && rightHip && shouldersCenter) {
			const hipsBone = getBone("Hips")
			const spineBone = getBone("Spine") ?? getBone("Chest") ?? getBone("UpperChest")
			const leftUpperLegBone = getBone("LeftUpperLeg")
			const rightUpperLegBone = getBone("RightUpperLeg")
			if (hipsBone && spineBone && leftUpperLegBone && rightUpperLegBone) {
				const parentWorldQ = getParentWorldQuaternion(hipsBone)
				const invParentQ = parentWorldQ.clone().invert()

				const restToSpine = spineBone.position.clone().normalize()
				const restToLeft = leftUpperLegBone.position.clone().normalize()
				const restToRight = rightUpperLegBone.position.clone().normalize()

				const targetToSpine = shouldersCenter.clone().sub(hipsCenter).normalize().applyQuaternion(invParentQ)
				const targetToLeft = leftHip.clone().sub(hipsCenter).normalize().applyQuaternion(invParentQ)
				const targetToRight = rightHip.clone().sub(hipsCenter).normalize().applyQuaternion(invParentQ)

				const qSpine = new THREE.Quaternion().setFromUnitVectors(restToSpine, targetToSpine)
				const qLeft = new THREE.Quaternion().setFromUnitVectors(restToLeft, targetToLeft)
				const qRight = new THREE.Quaternion().setFromUnitVectors(restToRight, targetToRight)

				const hipsTarget = qSpine.clone().slerp(qLeft, 0.25).slerp(qRight, 0.25)
				hipsBone.quaternion.slerp(hipsTarget, alpha)
				hipsBone.updateMatrixWorld(true)
			}
		}

		applyBoneBetweenPoints("Neck", "Head", neck, head, alpha)

		applyBoneBetweenPoints("LeftShoulder", "LeftUpperArm", leftShoulderInner, leftShoulder, alpha)
		applyBoneBetweenPoints("LeftUpperArm", "LeftLowerArm", leftShoulder, leftElbow, alpha)
		applyBoneBetweenPoints("LeftLowerArm", "LeftHand", leftElbow, leftWrist, alpha)

		applyBoneBetweenPoints("RightShoulder", "RightUpperArm", rightShoulderInner, rightShoulder, alpha)
		applyBoneBetweenPoints("RightUpperArm", "RightLowerArm", rightShoulder, rightElbow, alpha)
		applyBoneBetweenPoints("RightLowerArm", "RightHand", rightElbow, rightWrist, alpha)

		// const leftToeBase = leftHeel && leftFootIndex ? leftHeel.clone().lerp(leftFootIndex, 0.6) : leftFootIndex
		// const rightToeBase = rightHeel && rightFootIndex ? rightHeel.clone().lerp(rightFootIndex, 0.6) : rightFootIndex

		// applyBoneBetweenPoints("LeftUpperLeg", "LeftLowerLeg", leftHip, leftKnee, alpha)
		// applyBoneBetweenPoints("LeftLowerLeg", "LeftFoot", leftKnee, leftAnkle, alpha)
		// if (getBone("LeftToes")) {
		// 	applyBoneBetweenPoints("LeftFoot", "LeftToes", leftAnkle, leftToeBase, alpha)
		// }

		// applyBoneBetweenPoints("RightUpperLeg", "RightLowerLeg", rightHip, rightKnee, alpha)
		// applyBoneBetweenPoints("RightLowerLeg", "RightFoot", rightKnee, rightAnkle, alpha)
		// if (getBone("RightToes")) {
		// 	applyBoneBetweenPoints("RightFoot", "RightToes", rightAnkle, rightToeBase, alpha)
		// }

		return {
			leftWrist,
			rightWrist,
		}
	}

	const updateHandRig = (handLandmarks: LandmarkPoint[] | null | undefined, isRightHand: boolean, alpha: number) => {
		if (!handLandmarks) return

		const wrist = getLandmarkVector(getHandLandmark(handLandmarks, HandLandmark.Wrist))
		const indexMcp = getLandmarkVector(getHandLandmark(handLandmarks, HandLandmark.IndexFingerMCP))
		const middleMcp = getLandmarkVector(getHandLandmark(handLandmarks, HandLandmark.MiddleFingerMCP))
		const pinkyMcp = getLandmarkVector(getHandLandmark(handLandmarks, HandLandmark.PinkyMCP))

		if (wrist && indexMcp && middleMcp && pinkyMcp) {
			applyHandWristBasis(
				resolveBoneName("LeftHand", isRightHand),
				resolveBoneName("LeftIndexProximal", isRightHand),
				resolveBoneName("LeftMiddleProximal", isRightHand),
				resolveBoneName("LeftLittleProximal", isRightHand),
				wrist,
				indexMcp,
				middleMcp,
				pinkyMcp,
				alpha,
			)
		}

		for (const definition of Object.values(FINGER_DEFINITIONS)) {
			const mcp = getLandmarkVector(getHandLandmark(handLandmarks, definition.mcp))
			const pip = getLandmarkVector(getHandLandmark(handLandmarks, definition.pip))
			const dip = getLandmarkVector(getHandLandmark(handLandmarks, definition.dip))

			const [bone0, bone1, bone2] = definition.bones
			applyBoneBetweenPoints(resolveBoneName(bone0, isRightHand), resolveBoneName(bone1, isRightHand), mcp, pip, alpha)
			applyBoneBetweenPoints(resolveBoneName(bone1, isRightHand), resolveBoneName(bone2, isRightHand), pip, dip, alpha)
		}
	}

	const getLeftDistalFingerBone = (finger: LeftHandFinger) => {
		return getBone(LEFT_DISTAL_BONE_BY_FINGER[finger])
	}

	const getLeftDistalFingerWorldPosition = (finger: LeftHandFinger): THREE.Vector3 | null => {
		const bone = getLeftDistalFingerBone(finger)
		if (!bone) return null

		bone.updateWorldMatrix(true, false)
		const world = new THREE.Vector3()
		bone.getWorldPosition(world)
		return world
	}

	const update = (rawResults: HolisticResults) => {
		const results = normalizeHolisticResults(rawResults)
		// Initialize axes on first update (they're added but hidden/shown via setShowBoneAxes)
		if (!axesInitialized) {
			initializeBoneAxes()
		}

		if (!vrm) return

		const alpha = getAlpha()
		const poseLandmarks = results.poseLandmarks ?? null
		if (poseLandmarks) {
			updatePoseRig(poseLandmarks, alpha)
		}

		updateHandRig(results.leftHandLandmarks, false, alpha)
		updateHandRig(results.rightHandLandmarks, true, alpha)

		if (debugMode) {
			vrm.scene.updateMatrixWorld(true)
		}

		vrm?.update(1 / 60)
	}

	return {
		update,
		getBone,
		getLeftDistalFingerBone,
		getLeftDistalFingerWorldPosition,
		setShowBoneAxes,
	}
}
