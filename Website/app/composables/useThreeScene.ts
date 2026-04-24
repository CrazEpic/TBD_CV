import * as THREE from "three/webgpu"
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm"
import { ref } from "vue"

export const useThreeScene = (hostRef: any) => {
	const scene = ref<THREE.Scene | null>(null)
	const camera = ref<THREE.PerspectiveCamera | null>(null)
	const renderer = ref<any>(null)
	const controls = ref<OrbitControls | null>(null)

	let clock = new THREE.Clock()
	let raf = 0

	const init = async () => {
		scene.value = new THREE.Scene()
		scene.value.background = new THREE.Color(0x555555)

		renderer.value = new THREE.WebGPURenderer({ alpha: true, antialias: true })
		await renderer.value.init()

		hostRef.value.appendChild(renderer.value.domElement)

		camera.value = new THREE.PerspectiveCamera(35, 1, 0.1, 1000)
		camera.value.position.set(0, 1.4, 0.7)

		controls.value = new OrbitControls(camera.value, renderer.value.domElement)
		controls.value.target.set(0, 1.4, 0)
		controls.value.update()

		const light = new THREE.DirectionalLight(0xffffff)
		light.position.set(1, 1, 1).normalize()
		scene.value.add(light)

        scene.value.add(new THREE.AxesHelper(1))

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
		renderer.value.setPixelRatio(window.devicePixelRatio)
	}

	const startLoop = () => {
		const loop = () => {
			raf = requestAnimationFrame(loop)

			renderer.value?.render(scene.value!, camera.value!)
		}
		loop()
	}

	const loadVRM = async (path: string): Promise<VRM | null> => {
		const loader = new GLTFLoader()
		loader.register((p) => new VRMLoaderPlugin(p))

		const gltf: any = await new Promise((resolve, reject) => {
			loader.load(path, resolve, undefined, reject)
		})

		const vrm = gltf.userData.vrm as VRM
		if (!vrm) return null

		VRMUtils.removeUnnecessaryVertices(gltf.scene)
		VRMUtils.removeUnnecessaryJoints(gltf.scene)

		scene.value?.add(vrm.scene)
		vrm.scene.rotation.y = Math.PI

		return vrm
	}

	const update = (delta: number, vrm?: VRM | null) => {
		if (vrm) vrm.update(delta)
	}

	const dispose = () => {
		cancelAnimationFrame(raf)
		window.removeEventListener("resize", resize)
		renderer.value?.dispose()
		controls.value?.dispose()
	}

	return {
		scene,
		camera,
		renderer,
		controls,
		init,
		loadVRM,
		update,
		dispose,
	}
}
