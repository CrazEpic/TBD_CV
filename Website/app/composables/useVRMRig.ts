import * as THREE from "three"
import { VRM, VRMHumanBoneName } from "@pixiv/three-vrm"

export const useVRMRig = (vrm: VRM | null) => {
	const getBone = (name: keyof typeof VRMHumanBoneName) => {
		return vrm?.humanoid.getNormalizedBoneNode(VRMHumanBoneName[name])
	}

	const rigRotation = (name: keyof typeof VRMHumanBoneName, rot: { x: number; y: number; z: number }, damp = 1, lerp = 0.3) => {
		const bone = getBone(name)
		if (!bone) return

		const euler = new THREE.Euler(rot.x * damp, rot.y * damp, rot.z * damp)
		const quat = new THREE.Quaternion().setFromEuler(euler)

		bone.quaternion.slerp(quat, lerp)
	}

	const rigPosition = (name: keyof typeof VRMHumanBoneName, pos: { x: number; y: number; z: number }, damp = 1, lerp = 0.3) => {
		const bone = getBone(name)
		if (!bone) return

		const v = new THREE.Vector3(pos.x * damp, pos.y * damp, pos.z * damp)
		bone.position.lerp(v, lerp)
	}

	return {
		rigRotation,
		rigPosition,
	}
}
