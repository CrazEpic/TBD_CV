import * as THREE from "three"
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm"
import { shallowRef } from "vue"
import { usePropCalibration } from "@/composables/usePropCalibration"
import { useViolinKeypoints } from "@/composables/useViolinKeypoints"

export const useThreeScene = (hostRef: any) => {
	const scene = shallowRef<THREE.Scene | null>(null)
	const camera = shallowRef<THREE.PerspectiveCamera | null>(null)
	const renderer = shallowRef<any>(null)
	const controls = shallowRef<OrbitControls | null>(null)
	const currentVrm = shallowRef<VRM | null>(null)
	const propTools = usePropCalibration(scene)
	const { getDebugPoints, getFingeringPoints } = useViolinKeypoints()

	let clock = new THREE.Clock()
	let raf = 0
	const originalMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>()
	let wireframeMode = false


	const init = async () => {
		scene.value = new THREE.Scene()
		scene.value.background = new THREE.Color(0x9ed7b6)

		renderer.value = new THREE.WebGLRenderer({ alpha: true, antialias: true })

		hostRef.value.appendChild(renderer.value.domElement)

		camera.value = new THREE.PerspectiveCamera(35, 1, 0.1, 1000)
		camera.value.position.set(0, 1.4, 0.7)

		controls.value = new OrbitControls(camera.value, renderer.value.domElement)
		controls.value.target.set(0, 1.4, 0)
		controls.value.update()

		const light = new THREE.DirectionalLight(0xffffff)
		light.position.set(1, 1, 1).normalize()
		scene.value.add(light)

		scene.value.add(new THREE.AxesHelper(0.2))

		const loader = new GLTFLoader()
		const gltf = await loader.loadAsync("violin/scene.gltf")
		scene.value.add(gltf.scene)
		propTools.splitViolinAndBow(gltf.scene)
		// propTools.drawViolinKeypoints(getDebugPoints())
		propTools.drawViolinFingerings(getFingeringPoints(7))
		// propTools.drawViolinReferenceMarkers([0.575, 0.64])

		window.addEventListener("resize", resize)
		resize()

		startLoop()
	}

	const resize = () => {
		if (!renderer.value || !camera.value || !hostRef.value) return

		const w = hostRef.value.clientWidth
		const h = hostRef.value.clientHeight

		camera.value.aspect = w / Math.max(h, 1)
		camera.value.updateProjectionMatrix()

		renderer.value.setSize(w, h)
		renderer.value.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
	}

	const startLoop = () => {
		const loop = () => {
			raf = requestAnimationFrame(loop)
			const delta = clock.getDelta()
			if (currentVrm.value) {
				currentVrm.value.update(delta)
			}

			renderer.value?.render(scene.value!, camera.value!)
		}
		loop()
	}

	const loadVRM = async (path: string): Promise<VRM | null> => {
		const loader = new GLTFLoader()
		loader.register((parser) => new VRMLoaderPlugin(parser))

		const gltf: any = await new Promise((resolve, reject) => {
			loader.load(path, resolve, undefined, reject)
		})

		const vrm = gltf.userData.vrm as VRM
		if (!vrm) return null

		VRMUtils.removeUnnecessaryVertices(gltf.scene)
		VRMUtils.removeUnnecessaryJoints(gltf.scene)

		scene.value?.add(vrm.scene)
		vrm.scene.rotation.y = Math.PI
		currentVrm.value = vrm

		// Store original materials for wireframe toggle
		vrm.scene.traverse((obj: any) => {
			if (obj.isMesh && obj.material) {
				originalMaterials.set(obj, obj.material)
			}
		})

		return vrm
	}

	const setWireframeMode = (enabled: boolean) => {
		wireframeMode = enabled
		if (!currentVrm.value) return

		currentVrm.value.scene.traverse((obj: any) => {
			if (obj.isMesh) {
				if (enabled) {
					// Create wireframe material
					if (!obj.userData.wireframeMaterial) {
						obj.userData.wireframeMaterial = new THREE.MeshPhongMaterial({
							wireframe: true,
							color: 0xffffff,
							emissive: 0x333333,
						})
					}
					obj.material = obj.userData.wireframeMaterial
				} else {
					// Restore original material
					const originalMat = originalMaterials.get(obj)
					if (originalMat) {
						obj.material = originalMat
					}
				}
			}
		})
	}

	const update = (delta: number, vrm?: VRM | null) => {
		if (vrm) vrm.update(delta)
	}

	const loadPropCalibrationFromUrl = async (url: string) => {
		const response = await fetch(url, { cache: "no-store" })
		if (!response.ok) {
			throw new Error(`Calibration file not found: ${url}`)
		}
		const raw = await response.text()
		propTools.importPropCalibration(raw)
	}

	const dispose = () => {
		cancelAnimationFrame(raf)
		window.removeEventListener("resize", resize)
		renderer.value?.dispose()
		controls.value?.dispose()
		currentVrm.value = null
		propTools.dispose()
	}

	return {
		scene,
		camera,
		renderer,
		controls,
		init,
		loadVRM,
		update,
		setWireframeMode,
		setPropCalibration: propTools.setPropCalibration,
		setPropPoseParent: propTools.setPropPoseParent,
		setPropPoseTransform: propTools.setPropPoseTransform,
		setPropParentDefaults: propTools.setPropParentDefaults,
		getPropCalibration: propTools.getPropCalibration,
		getPropParentDefaults: propTools.getPropParentDefaults,
		resetPropCalibration: propTools.resetPropCalibration,
		resetPropParentDefaults: propTools.resetPropParentDefaults,
		bakeCalibrationIntoParentDefaults: propTools.bakeCalibrationIntoParentDefaults,
		getPropMeasurement: propTools.getPropMeasurement,
		fitPropZLengthCm: propTools.fitPropZLengthCm,
		exportPropCalibration: propTools.exportPropCalibration,
		importPropCalibration: propTools.importPropCalibration,
		loadPropCalibrationFromUrl,
		getPropDiagnostics: propTools.getPropDiagnostics,
		getPropTransformOffset: propTools.getPropTransformOffset,
		drawViolinReferenceMarkers: propTools.drawViolinReferenceMarkers,
		getViolinFingeringWorldPoint: propTools.getViolinFingeringWorldPoint,
		getViolinFingeringWorldPointByName: propTools.getViolinFingeringWorldPointByName,
		getViolinFingeringWorldPoints: propTools.getViolinFingeringWorldPoints,
		dispose,
	}
}
