import * as THREE from "three/webgpu"
import { VRMHumanBoneName } from "@pixiv/three-vrm"

type Vec3 = { x: number; y: number; z: number }

type PropTransformState = {
	position: Vec3
	rotationDeg: Vec3
	scale: Vec3
}

const deg30 = THREE.MathUtils.degToRad(30)

const midpoint = (a: Vec3, b: Vec3): Vec3 => ({
	x: (a.x + b.x) * 0.5,
	y: (a.y + b.y) * 0.5,
	z: (a.z + b.z) * 0.5,
})

type ViolinRig = {
	getBone: (name: keyof typeof VRMHumanBoneName) => THREE.Object3D | null
}

const getWorldPoint = (bone: THREE.Object3D | null): Vec3 | null => {
	if (!bone) return null
	const position = new THREE.Vector3()
	bone.getWorldPosition(position)
	return { x: position.x, y: position.y, z: position.z }
}

const subtract = (a: Vec3, b: Vec3): THREE.Vector3 => new THREE.Vector3(a.x - b.x, a.y - b.y, a.z - b.z)

export const useViolinPose = () => {
	let previousAnchor: THREE.Vector3 | null = null

	const estimate = (rig: ViolinRig | null): PropTransformState | null => {
		if (!rig) return null

		const leftShoulder = getWorldPoint(rig.getBone("LeftShoulder"))
		const rightShoulder = getWorldPoint(rig.getBone("RightShoulder"))
		const leftLowerArm = getWorldPoint(rig.getBone("LeftLowerArm"))
		const leftHand = getWorldPoint(rig.getBone("LeftHand"))
		const leftIndex = getWorldPoint(rig.getBone("LeftIndexProximal"))
		const leftPinky = getWorldPoint(rig.getBone("LeftLittleProximal"))
		const hips = getWorldPoint(rig.getBone("Hips"))
		const chest = getWorldPoint(rig.getBone("Chest") ?? rig.getBone("UpperChest") ?? rig.getBone("Spine"))

		if (!leftShoulder || !rightShoulder || !leftHand || !hips || !chest) return null

		const anchorPoint = midpoint(leftShoulder, rightShoulder)
		let anchor = new THREE.Vector3(anchorPoint.x, anchorPoint.y, anchorPoint.z)
		if (previousAnchor) {
			anchor = previousAnchor.clone().lerp(anchor, 0.2)
		}
		previousAnchor = anchor.clone()

		const torsoUp = subtract(chest, hips)
		if (torsoUp.lengthSq() < 1e-8) return null
		torsoUp.normalize()

		const palmTarget = new THREE.Vector3(leftHand.x, leftHand.y, leftHand.z)
		if (leftLowerArm && leftIndex && leftPinky) {
			const wrist = new THREE.Vector3(leftHand.x, leftHand.y, leftHand.z)
			const index = new THREE.Vector3(leftIndex.x, leftIndex.y, leftIndex.z)
			const pinky = new THREE.Vector3(leftPinky.x, leftPinky.y, leftPinky.z)
			const across = pinky.clone().sub(index)
			const palmForward = index.clone().add(pinky).multiplyScalar(0.5).sub(wrist)
			if (across.lengthSq() >= 1e-8 && palmForward.lengthSq() >= 1e-8) {
				across.normalize()
				palmForward.normalize()
				const palmNormal = new THREE.Vector3().crossVectors(across, palmForward)
				if (palmNormal.lengthSq() >= 1e-8) {
					palmNormal.normalize()
					if (palmNormal.dot(torsoUp) < 0) palmNormal.multiplyScalar(-1)
					palmTarget.addScaledVector(palmNormal, 0.06)
				}
			}
		} else {
			palmTarget.addScaledVector(torsoUp, 0.04)
		}

		const forward = palmTarget.sub(anchor)
		if (forward.lengthSq() < 1e-8) return null
		forward.normalize()

		const right = new THREE.Vector3().crossVectors(forward, torsoUp)
		if (right.lengthSq() < 1e-8) return null
		right.normalize()

		const up = new THREE.Vector3().crossVectors(right, forward).normalize()
		const tiltedUp = up.clone().multiplyScalar(Math.cos(deg30)).add(right.clone().multiplyScalar(Math.sin(deg30))).normalize()
		const tiltedRight = new THREE.Vector3().crossVectors(forward, tiltedUp).normalize()

		const rotation = new THREE.Euler().setFromRotationMatrix(
			new THREE.Matrix4().makeBasis(tiltedRight, tiltedUp, forward),
		)

		return {
			position: { x: anchor.x, y: anchor.y, z: anchor.z },
			rotationDeg: {
				x: THREE.MathUtils.radToDeg(rotation.x),
				y: THREE.MathUtils.radToDeg(rotation.y),
				z: THREE.MathUtils.radToDeg(rotation.z + Math.PI*5/4),
			},
			scale: { x: 1, y: 1, z: 1 },
		}
	}

	return {
		estimate,
	}
}
