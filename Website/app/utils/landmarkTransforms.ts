import { type HolisticResults } from "@/utils/landmarks"

const cloneLandmarks = (landmarks: HolisticResults[keyof HolisticResults]) => {
	return landmarks?.map((landmark) => ({ ...landmark })) ?? null
}

export const cloneHolisticResults = (results: HolisticResults): HolisticResults => {
	return {
		poseLandmarks: cloneLandmarks(results.poseLandmarks),
		leftHandLandmarks: cloneLandmarks(results.leftHandLandmarks),
		rightHandLandmarks: cloneLandmarks(results.rightHandLandmarks),
		faceLandmarks: cloneLandmarks(results.faceLandmarks),
	}
}

export const normalizeHolisticResults = (results: HolisticResults): HolisticResults => {
	const normalized = cloneHolisticResults(results)
	const flipY = -1
	const flipZ = -1

	const applyFlip = (landmarks: HolisticResults[keyof HolisticResults]) => {
		return landmarks?.map((landmark) => ({
			...landmark,
			y: landmark.y * flipY,
			z: (landmark.z ?? 0) * flipZ,
		})) ?? null
	}

	normalized.poseLandmarks = applyFlip(normalized.poseLandmarks)
	normalized.leftHandLandmarks = applyFlip(normalized.leftHandLandmarks)
	normalized.rightHandLandmarks = applyFlip(normalized.rightHandLandmarks)
	normalized.faceLandmarks = applyFlip(normalized.faceLandmarks)

	return normalized
}