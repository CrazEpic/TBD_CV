import { Holistic } from "@mediapipe/holistic"
import { Camera } from "@mediapipe/camera_utils"

export const useMediaPipeHolistic = (videoRef: any) => {
	const holistic = ref<Holistic | null>(null)
	let camera: Camera | null = null

	let onResultsCallback: ((results: any) => void) | null = null

	const setOnResults = (cb: (results: any) => void) => {
		onResultsCallback = cb
	}

	const init = async (baseUrl: string) => {
		holistic.value = new Holistic({
			locateFile: (file) => `${baseUrl}mediapipe/holistic/${file}`,
		})

		holistic.value.setOptions({
			modelComplexity: 0,
			smoothLandmarks: true,
			refineFaceLandmarks: true,
			minDetectionConfidence: 0.7,
			minTrackingConfidence: 0.7,
		})

		holistic.value.onResults((results) => {
			onResultsCallback?.(results)
		})
	}

	const start = async () => {
		if (!videoRef.value) return

		camera = new Camera(videoRef.value, {
			width: 640,
			height: 480,
			onFrame: async () => {
				if (holistic.value && videoRef.value) {
					await holistic.value.send({ image: videoRef.value })
				}
			},
		})

		camera.start()
	}

	const stop = () => {
		camera?.stop?.()
		holistic.value?.close?.()
	}

	return {
		holistic,
		init,
		start,
		stop,
		setOnResults,
	}
}
