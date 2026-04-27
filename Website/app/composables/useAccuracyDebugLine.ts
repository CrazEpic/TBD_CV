import * as THREE from "three"
import type { Ref } from "vue"
import type { FingerAccuracyReading } from "@/composables/useViolinFingerAccuracy"

export const useAccuracyDebugLine = (sceneRef: Ref<THREE.Scene | null>) => {
	const positions = new Float32Array(6)
	const geometry = new THREE.BufferGeometry()
	const positionAttribute = new THREE.BufferAttribute(positions, 3)
	geometry.setAttribute("position", positionAttribute)

	const material = new THREE.LineBasicMaterial({
		color: 0xa855f7,
		transparent: true,
		opacity: 0.95,
	})

	const line = new THREE.Line(geometry, material)
	line.name = "FingerAccuracyDebugLine"
	line.visible = false
	line.frustumCulled = false

	const ensureAttached = () => {
		const scene = sceneRef.value
		if (!scene) return
		if (line.parent === scene) return
		scene.add(line)
	}

	const hide = () => {
		line.visible = false
	}

	const update = (reading: FingerAccuracyReading | null) => {
		ensureAttached()
		if (!reading?.targetWorld || !reading.fingerWorld) {
			hide()
			return
		}

		positions[0] = reading.targetWorld.x
		positions[1] = reading.targetWorld.y
		positions[2] = reading.targetWorld.z
		positions[3] = reading.fingerWorld.x
		positions[4] = reading.fingerWorld.y
		positions[5] = reading.fingerWorld.z
		positionAttribute.needsUpdate = true
		line.visible = true
	}

	const dispose = () => {
		line.removeFromParent()
		geometry.dispose()
		material.dispose()
	}

	return {
		line,
		update,
		hide,
		dispose,
	}
}
