import { reactive } from "vue"
import { type HolisticResults, type LandmarkPoint, HandLandmark, PoseLandmark, getHandLandmark, getPoseLandmark } from "@/utils/landmarks"
import { normalizeHolisticResults } from "@/utils/landmarkTransforms"

// mediapipe
// (from camera perspective)
// positive z is distance from cam
// positive x is right of cam
// positive y is down of cam

// need to flip y and z for three.js

export const usePoseStream = () => {
	const state = reactive({
		pose: null as LandmarkPoint[] | null,
		hands: null as { left: LandmarkPoint[] | null; right: LandmarkPoint[] | null } | null,
		face: null as LandmarkPoint[] | null,
	})

	const update = (results: HolisticResults) => {
		const normalized = normalizeHolisticResults(results)

		state.pose = normalized.poseLandmarks
		state.hands = {
			left: normalized.leftHandLandmarks,
			right: normalized.rightHandLandmarks,
		}
		state.face = normalized.faceLandmarks
	}

	const getPose = (landmark: PoseLandmark) => {
		return getPoseLandmark(state.pose, landmark)
	}

	const getHand = (landmark: HandLandmark, left = true) => {
		return left ? getHandLandmark(state.hands?.left, landmark) : getHandLandmark(state.hands?.right, landmark)
	}

	return {
		state,
		update,
		getPose,
		getHand,
	}
}
