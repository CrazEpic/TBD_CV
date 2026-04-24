import { reactive } from "vue"

export const usePoseStream = () => {
	const state = reactive({
		pose: null,
		hands: null,
		face: null,
	})

	const update = (results: any) => {
		state.pose = results.poseLandmarks
		state.hands = {
			left: results.leftHandLandmarks,
			right: results.rightHandLandmarks,
		}
		state.face = results.faceLandmarks
	}

	const getPose = (i: number) => {
		return state.pose?.[i]
	}

	const getHand = (i: number, left = true) => {
		return left ? state.hands?.left?.[i] : state.hands?.right?.[i]
	}

	return {
		state,
		update,
		getPose,
		getHand,
	}
}
