import * as THREE from "three"
import { ref, shallowRef, type Ref } from "vue"

type PropId = "violin" | "bow"
type Axis = "x" | "y" | "z"

type Vec3State = Record<Axis, number>

type PropTransformState = {
	position: Vec3State
	rotationDeg: Vec3State
	scale: Vec3State
}

type PropCalibration = {
	position: Vec3State
	rotationDeg: Vec3State
	scale: Vec3State
	visible: boolean
}

type PropCalibrationMap = Record<PropId, PropCalibration>
type PropParentDefaultsMap = Record<PropId, PropTransformState>
type PropPoseMap = Record<PropId, PropTransformState>

type PropMeasurement = {
	sizeMeters: Vec3State
	zMeters: number
	zCm: number
}

type PropTransformOffset = {
	parent: PropTransformState
	root: PropTransformState
}

type TransformSnapshot = {
	position: THREE.Vector3
	rotation: THREE.Euler
	scale: THREE.Vector3
}

type DebugPoint = {
	name: string
	position: [number, number, number]
	group?: string
}

export type ViolinFingeringWorldPoint = {
	name: string
	world: THREE.Vector3
}

export const usePropCalibration = (sceneRef: Ref<any>) => {
	const violinDebugFingeringsGroupRef = shallowRef<THREE.Group | null>(null)
	const propParents = {
		violin: shallowRef<THREE.Group | null>(null),
		bow: shallowRef<THREE.Group | null>(null),
	}
	const propPoseParents = {
		violin: shallowRef<THREE.Group | null>(null),
		bow: shallowRef<THREE.Group | null>(null),
	}
	const propModelRoots = {
		violin: shallowRef<THREE.Group | null>(null),
		bow: shallowRef<THREE.Group | null>(null),
	}
	const propDebugRoots = {
		violin: shallowRef<THREE.Group | null>(null),
		bow: shallowRef<THREE.Group | null>(null),
	}
	const propDiagnostics = ref<Record<PropId, { branchName: string; meshCount: number }>>({
		violin: { branchName: "", meshCount: 0 },
		bow: { branchName: "", meshCount: 0 },
	})
	const baseParentSnapshots = new Map<PropId, TransformSnapshot>()
	const baseRootSnapshots = new Map<PropId, TransformSnapshot>()
	let violinDebugKeypointsGroup: THREE.Group | null = null
	let violinDebugFingeringsGroup: THREE.Group | null = null
	let violinReferenceMarkersGroup: THREE.Group | null = null

	const clearDebugGroup = (group: THREE.Group | null) => {
		if (!group) return
		group.traverse((obj) => {
			if (!(obj as THREE.Mesh).isMesh) return
			const mesh = obj as THREE.Mesh
			mesh.geometry?.dispose()
			if (Array.isArray(mesh.material)) {
				mesh.material.forEach((material) => material.dispose())
			} else {
				mesh.material?.dispose()
			}
		})
		group.removeFromParent()
	}

	const clearViolinDebugMarkers = () => {
		clearDebugGroup(violinDebugKeypointsGroup)
		clearDebugGroup(violinDebugFingeringsGroup)
		clearDebugGroup(violinReferenceMarkersGroup)
		violinDebugKeypointsGroup = null
		violinDebugFingeringsGroup = null
		violinReferenceMarkersGroup = null
	}

	const defaultTransformState = (): PropTransformState => ({
		position: { x: 0.04, y: -0.04, z: 0 },
		rotationDeg: { x: 0, y: 135, z: 0 },
		scale: { x: 1, y: 1, z: 1 },
	})

	const defaultPropCalibration = (): PropCalibrationMap => ({
		violin: {
			...defaultTransformState(),
			visible: true,
		},
		bow: {
			...defaultTransformState(),
			visible: true,
		},
	})

	const defaultPropParentDefaults = (): PropParentDefaultsMap => ({
		violin: defaultTransformState(),
		bow: defaultTransformState(),
	})

	const defaultPropPoseTransforms = (): PropPoseMap => ({
		violin: defaultTransformState(),
		bow: defaultTransformState(),
	})

	const propCalibration = ref<PropCalibrationMap>(defaultPropCalibration())
	const propParentDefaults = ref<PropParentDefaultsMap>(defaultPropParentDefaults())
	const propPoseTransforms = ref<PropPoseMap>(defaultPropPoseTransforms())

	const cloneCalibration = () => JSON.parse(JSON.stringify(propCalibration.value)) as PropCalibrationMap
	const cloneParentDefaults = () => JSON.parse(JSON.stringify(propParentDefaults.value)) as PropParentDefaultsMap

	const countMeshes = (root: THREE.Object3D) => {
		let count = 0
		root.traverse((obj) => {
			if ((obj as THREE.Mesh).isMesh) count++
		})
		return count
	}

	const getBranchCandidates = (root: THREE.Object3D): THREE.Object3D[] => {
		const direct = root.children.filter((child) => child.type !== "Bone")
		if (direct.length >= 2) return direct
		return root.children
	}

	const applyTransformState = (target: THREE.Object3D, state: PropTransformState) => {
		target.position.set(state.position.x, state.position.y, state.position.z)
		target.rotation.set(THREE.MathUtils.degToRad(state.rotationDeg.x), THREE.MathUtils.degToRad(state.rotationDeg.y), THREE.MathUtils.degToRad(state.rotationDeg.z))
		target.scale.set(state.scale.x, state.scale.y, state.scale.z)
	}

	const snapshotTransform = (target: THREE.Object3D): TransformSnapshot => ({
		position: target.position.clone(),
		rotation: target.rotation.clone(),
		scale: target.scale.clone(),
	})

	const createTransformOffset = (target: THREE.Object3D, base: TransformSnapshot): PropTransformState => ({
		position: {
			x: target.position.x - base.position.x,
			y: target.position.y - base.position.y,
			z: target.position.z - base.position.z,
		},
		rotationDeg: {
			x: THREE.MathUtils.radToDeg(target.rotation.x - base.rotation.x),
			y: THREE.MathUtils.radToDeg(target.rotation.y - base.rotation.y),
			z: THREE.MathUtils.radToDeg(target.rotation.z - base.rotation.z),
		},
		scale: {
			x: Math.abs(base.scale.x) > 1e-8 ? target.scale.x / base.scale.x : target.scale.x,
			y: Math.abs(base.scale.y) > 1e-8 ? target.scale.y / base.scale.y : target.scale.y,
			z: Math.abs(base.scale.z) > 1e-8 ? target.scale.z / base.scale.z : target.scale.z,
		},
	})

	const applyParentTransform = (propId: PropId) => {
		const parent = propParents[propId].value
		if (!parent) return
		applyTransformState(parent, propParentDefaults.value[propId])
	}

	const applyPoseTransform = (propId: PropId) => {
		const parent = propPoseParents[propId].value
		if (!parent) return
		applyTransformState(parent, propPoseTransforms.value[propId])
	}

	const setPropPoseParent = (propId: PropId, parent: THREE.Object3D | null) => {
		const poseParent = propPoseParents[propId].value
		if (!poseParent) return

		if (parent) {
			parent.add(poseParent)
		} else if (sceneRef.value) {
			sceneRef.value.add(poseParent)
		}

		applyPoseTransform(propId)
	}

	const applyPropTransform = (propId: PropId) => {
		const root = propModelRoots[propId].value
		if (!root) return

		const cfg = propCalibration.value[propId]
		applyTransformState(root, cfg)
		root.visible = cfg.visible
	}

	const splitViolinAndBow = (gltfScene: THREE.Object3D) => {
		const rootNode = gltfScene.getObjectByName("RootNode") ?? gltfScene
		const branches = getBranchCandidates(rootNode)
		if (!branches.length) return

		const sorted = [...branches].map((node) => ({ node, meshCount: countMeshes(node) })).sort((a, b) => b.meshCount - a.meshCount)

		const violinBranch = sorted[0]?.node ?? null
		const bowBranch = sorted[1]?.node ?? null
		if (!violinBranch || !bowBranch || !sceneRef.value) return

		const violinRoot = new THREE.Group()
		violinRoot.name = "ViolinRoot"
		const bowRoot = new THREE.Group()
		bowRoot.name = "BowRoot"
		const violinPoseParent = new THREE.Group()
		violinPoseParent.name = "ViolinPoseParent"
		const bowPoseParent = new THREE.Group()
		bowPoseParent.name = "BowPoseParent"
		const violinDebugRoot = new THREE.Group()
		violinDebugRoot.name = "ViolinDebugRoot"
		const bowDebugRoot = new THREE.Group()
		bowDebugRoot.name = "BowDebugRoot"
		const violinParent = new THREE.Group()
		violinParent.name = "ViolinParent"
		const bowParent = new THREE.Group()
		bowParent.name = "BowParent"

		sceneRef.value.add(violinPoseParent)
		sceneRef.value.add(bowPoseParent)
		violinPoseParent.add(violinParent)
		bowPoseParent.add(bowParent)
		violinParent.add(violinRoot)
		bowParent.add(bowRoot)
		violinParent.add(violinDebugRoot)
		bowParent.add(bowDebugRoot)
		violinRoot.attach(violinBranch)
		bowRoot.attach(bowBranch)

		propParents.violin.value = violinParent
		propParents.bow.value = bowParent
		propPoseParents.violin.value = violinPoseParent
		propPoseParents.bow.value = bowPoseParent
		propModelRoots.violin.value = violinRoot
		propModelRoots.bow.value = bowRoot
		propDebugRoots.violin.value = violinDebugRoot
		propDebugRoots.bow.value = bowDebugRoot
		baseParentSnapshots.set("violin", snapshotTransform(violinParent))
		baseParentSnapshots.set("bow", snapshotTransform(bowParent))
		baseRootSnapshots.set("violin", snapshotTransform(violinRoot))
		baseRootSnapshots.set("bow", snapshotTransform(bowRoot))

		propDiagnostics.value = {
			violin: { branchName: violinBranch.name || "(unnamed)", meshCount: countMeshes(violinBranch) },
			bow: { branchName: bowBranch.name || "(unnamed)", meshCount: countMeshes(bowBranch) },
		}

		applyParentTransform("violin")
		applyParentTransform("bow")
		applyPoseTransform("violin")
		applyPoseTransform("bow")
		applyPropTransform("violin")
		applyPropTransform("bow")
	}

	const setPropPoseTransform = (propId: PropId, pose: Partial<PropTransformState>) => {
		const current = propPoseTransforms.value[propId]
		propPoseTransforms.value[propId] = {
			position: { ...current.position, ...(pose.position ?? {}) },
			rotationDeg: { ...current.rotationDeg, ...(pose.rotationDeg ?? {}) },
			scale: { ...current.scale, ...(pose.scale ?? {}) },
		}
		applyPoseTransform(propId)
	}

	const setPropCalibration = (propId: PropId, calibration: Partial<PropCalibration>) => {
		const current = propCalibration.value[propId]
		propCalibration.value[propId] = {
			position: { ...current.position, ...(calibration.position ?? {}) },
			rotationDeg: { ...current.rotationDeg, ...(calibration.rotationDeg ?? {}) },
			scale: { ...current.scale, ...(calibration.scale ?? {}) },
			visible: calibration.visible ?? current.visible,
		}
		applyPropTransform(propId)
	}

	const buildMarkerGroup = (groupName: string, points: DebugPoint[], color: number, radius = 0.0075) => {
		const group = new THREE.Group()
		group.name = groupName

		points.forEach((point) => {
			const geometry = new THREE.SphereGeometry(radius, 12, 12)
			const material = new THREE.MeshBasicMaterial({ color })
			const marker = new THREE.Mesh(geometry, material)
			marker.name = point.name
			marker.position.set(point.position[0], point.position[1], point.position[2])
			group.add(marker)
		})

		return group
	}

	const drawViolinKeypoints = (points: DebugPoint[]) => {
		const violinDebugRoot = propDebugRoots.violin.value
		if (!violinDebugRoot || !points.length) return
		clearDebugGroup(violinDebugKeypointsGroup)
		violinDebugKeypointsGroup = buildMarkerGroup("ViolinDebugKeypoints", points, 0x22d3ee, 0.003)
		violinDebugRoot.add(violinDebugKeypointsGroup)
	}

	const drawViolinFingerings = (points: DebugPoint[]) => {
		const violinDebugRoot = propDebugRoots.violin.value
		if (!violinDebugRoot || !points.length) return
		clearDebugGroup(violinDebugFingeringsGroup)
		violinDebugFingeringsGroup = buildMarkerGroup("ViolinDebugFingerings", points, 0xef4444, 0.003)
		violinDebugRoot.add(violinDebugFingeringsGroup)
		violinDebugFingeringsGroupRef.value = violinDebugFingeringsGroup
	}

	const getViolinFingeringWorldPointByName = (name: string): THREE.Vector3 | null => {
		const group = violinDebugFingeringsGroupRef.value
		if (!group) return null

		const debugFingerings = getViolinDebugFingerings.value ?? []
		const match = debugFingerings.find((entry) => entry.name === name)
		if (!match) return null

		group.updateWorldMatrix(true, false)
		return match.position.clone().applyMatrix4(group.matrixWorld)
	}

	const getViolinFingeringWorldPoint = (stringName: "G" | "D" | "A" | "E", positionOnString: number): THREE.Vector3 | null => {
		if (!Number.isFinite(positionOnString) || positionOnString < 0) return null
		const pointName = `fingering_${stringName}_${Math.floor(positionOnString)}`
		return getViolinFingeringWorldPointByName(pointName)
	}

	const getViolinFingeringWorldPoints = (): ViolinFingeringWorldPoint[] => {
		const group = violinDebugFingeringsGroupRef.value
		if (!group) return []

		group.updateWorldMatrix(true, false)
		const debugFingerings = getViolinDebugFingerings.value ?? []
		return debugFingerings.map((entry) => ({
			name: entry.name,
			world: entry.position.clone().applyMatrix4(group.matrixWorld),
		}))
	}

	const drawViolinReferenceMarkers = (zValues: number[] = [0.575, 0.64]) => {
		const violinDebugRoot = propDebugRoots.violin.value
		if (!violinDebugRoot || !zValues.length) return

		clearDebugGroup(violinReferenceMarkersGroup)
		const group = new THREE.Group()
		group.name = "ViolinReferenceMarkers"

		for (const z of zValues) {
			if (!Number.isFinite(z)) continue
			const marker = new THREE.Mesh(new THREE.SphereGeometry(0.014, 20, 20), new THREE.MeshBasicMaterial({ color: 0xff00ff }))
			marker.name = `violin_ref_z_${z.toFixed(3)}`
			marker.position.set(0, 0, z)
			group.add(marker)
		}

		violinReferenceMarkersGroup = group
		violinDebugRoot.add(group)
	}

	const getPropTransformOffset = (propId: PropId): PropTransformOffset | null => {
		const parent = propParents[propId].value
		const root = propModelRoots[propId].value
		const baseParent = baseParentSnapshots.get(propId)
		const baseRoot = baseRootSnapshots.get(propId)
		if (!parent || !root || !baseParent || !baseRoot) return null

		return {
			parent: createTransformOffset(parent, baseParent),
			root: createTransformOffset(root, baseRoot),
		}
	}

	const setPropParentDefaults = (propId: PropId, defaults: Partial<PropTransformState>) => {
		const current = propParentDefaults.value[propId]
		propParentDefaults.value[propId] = {
			position: { ...current.position, ...(defaults.position ?? {}) },
			rotationDeg: { ...current.rotationDeg, ...(defaults.rotationDeg ?? {}) },
			scale: { ...current.scale, ...(defaults.scale ?? {}) },
		}
		applyParentTransform(propId)
	}

	const getPropCalibration = () => cloneCalibration()
	const getPropParentDefaults = () => cloneParentDefaults()

	const resetPropParentDefaults = (propId?: PropId) => {
		const defaults = defaultPropParentDefaults()
		if (propId) {
			propParentDefaults.value[propId] = defaults[propId]
			applyParentTransform(propId)
			return
		}

		propParentDefaults.value = defaults
		applyParentTransform("violin")
		applyParentTransform("bow")
		applyPoseTransform("violin")
		applyPoseTransform("bow")
	}

	const resetPropCalibration = (propId?: PropId) => {
		const defaults = defaultPropCalibration()
		if (propId) {
			propCalibration.value[propId] = defaults[propId]
			applyPropTransform(propId)
			return
		}

		propCalibration.value = defaults
		applyPropTransform("violin")
		applyPropTransform("bow")
	}

	const bakeCalibrationIntoParentDefaults = (propId: PropId) => {
		const parentDefaults = propParentDefaults.value[propId]
		const currentCalibration = propCalibration.value[propId]

		setPropParentDefaults(propId, {
			position: {
				x: parentDefaults.position.x + currentCalibration.position.x,
				y: parentDefaults.position.y + currentCalibration.position.y,
				z: parentDefaults.position.z + currentCalibration.position.z,
			},
			rotationDeg: {
				x: parentDefaults.rotationDeg.x + currentCalibration.rotationDeg.x,
				y: parentDefaults.rotationDeg.y + currentCalibration.rotationDeg.y,
				z: parentDefaults.rotationDeg.z + currentCalibration.rotationDeg.z,
			},
			scale: {
				x: parentDefaults.scale.x * currentCalibration.scale.x,
				y: parentDefaults.scale.y * currentCalibration.scale.y,
				z: parentDefaults.scale.z * currentCalibration.scale.z,
			},
		})

		resetPropCalibration(propId)
	}

	const getPropMeasurement = (propId: PropId): PropMeasurement | null => {
		const target = propModelRoots[propId].value
		if (!target) return null

		const box = new THREE.Box3().setFromObject(target)
		if (box.isEmpty()) {
			return {
				sizeMeters: { x: 0, y: 0, z: 0 },
				zMeters: 0,
				zCm: 0,
			}
		}

		const size = new THREE.Vector3()
		box.getSize(size)

		return {
			sizeMeters: { x: size.x, y: size.y, z: size.z },
			zMeters: size.z,
			zCm: size.z * 100,
		}
	}

	const fitPropZLengthCm = (propId: PropId, targetCm: number) => {
		if (!Number.isFinite(targetCm) || targetCm <= 0) return
		const measurement = getPropMeasurement(propId)
		if (!measurement || measurement.zMeters <= 1e-6) return

		const factor = targetCm / 100 / measurement.zMeters
		const current = propCalibration.value[propId]
		setPropCalibration(propId, {
			scale: {
				x: current.scale.x * factor,
				y: current.scale.y * factor,
				z: current.scale.z * factor,
			},
		})
	}

	const exportPropCalibration = () =>
		JSON.stringify(
			{
				calibration: propCalibration.value,
				parentDefaults: propParentDefaults.value,
			},
			null,
			2
		)

	const importPropCalibration = (rawJson: string) => {
		const parsed = JSON.parse(rawJson) as
			| Partial<PropCalibrationMap>
			| {
					calibration?: Partial<PropCalibrationMap>
					parentDefaults?: Partial<PropParentDefaultsMap>
			  }

		if ("calibration" in parsed || "parentDefaults" in parsed) {
			if (parsed.parentDefaults?.violin) setPropParentDefaults("violin", parsed.parentDefaults.violin)
			if (parsed.parentDefaults?.bow) setPropParentDefaults("bow", parsed.parentDefaults.bow)
			if (parsed.calibration?.violin) setPropCalibration("violin", parsed.calibration.violin)
			if (parsed.calibration?.bow) setPropCalibration("bow", parsed.calibration.bow)
			return
		}

		const legacy = parsed as Partial<PropCalibrationMap>
		if (legacy.violin) setPropCalibration("violin", legacy.violin)
		if (legacy.bow) setPropCalibration("bow", legacy.bow)
	}

	const getPropDiagnostics = () => propDiagnostics.value

	const dispose = () => {
		clearViolinDebugMarkers()
		baseParentSnapshots.clear()
		baseRootSnapshots.clear()
		propParents.violin.value = null
		propParents.bow.value = null
		propPoseParents.violin.value = null
		propPoseParents.bow.value = null
		propModelRoots.violin.value = null
		propModelRoots.bow.value = null
		propDebugRoots.violin.value = null
		propDebugRoots.bow.value = null
	}

	const getViolinDebugFingerings = computed(() => {
		return violinDebugFingeringsGroupRef.value?.children.map((child) => {
			return {
				name: child.name,
				position: child.position.clone(),
			}
		})
	})

	return {
		getViolinDebugFingerings,
		splitViolinAndBow,
		setPropCalibration,
		setPropPoseParent,
		setPropPoseTransform,
		setPropParentDefaults,
		getPropCalibration,
		getPropParentDefaults,
		resetPropCalibration,
		resetPropParentDefaults,
		bakeCalibrationIntoParentDefaults,
		getPropMeasurement,
		fitPropZLengthCm,
		exportPropCalibration,
		importPropCalibration,
		getPropDiagnostics,
		drawViolinKeypoints,
		drawViolinFingerings,
		drawViolinReferenceMarkers,
		getViolinFingeringWorldPointByName,
		getViolinFingeringWorldPoint,
		getViolinFingeringWorldPoints,
		getPropTransformOffset,
		dispose,
	}
}
