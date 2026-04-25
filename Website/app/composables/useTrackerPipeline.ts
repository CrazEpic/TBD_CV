import { ref } from "vue"
import { type HolisticResults } from "@/utils/landmarks"

export type TrackerFrame = {
	results: HolisticResults
	timestamp: number
	source: "webcam" | "video"
}

export type TrackerStage = {
	name: string
	run: (frame: TrackerFrame) => TrackerFrame | void | Promise<TrackerFrame | void>
}

export const useTrackerPipeline = () => {
	const stages = ref<TrackerStage[]>([])

	const removeStage = (name: string) => {
		stages.value = stages.value.filter((stage) => stage.name !== name)
	}

	const registerStage = (name: string, run: TrackerStage["run"], beforeStageName?: string) => {
		const stage = { name, run }
		if (!beforeStageName) {
			stages.value.push(stage)
			return () => removeStage(name)
		}

		const index = stages.value.findIndex((entry) => entry.name === beforeStageName)
		if (index === -1) {
			stages.value.push(stage)
		} else {
			stages.value.splice(index, 0, stage)
		}

		return () => removeStage(name)
	}

	const clearStages = () => {
		stages.value = []
	}

	const process = async (frame: TrackerFrame) => {
		let currentFrame = frame
		for (const stage of stages.value) {
			const nextFrame = await stage.run(currentFrame)
			if (nextFrame) {
				currentFrame = nextFrame
			}
		}
		return currentFrame
	}

	return {
		stages,
		registerStage,
		removeStage,
		clearStages,
		process,
	}
}