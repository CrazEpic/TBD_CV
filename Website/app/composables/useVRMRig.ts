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
