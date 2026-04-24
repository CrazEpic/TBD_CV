import { ref } from "vue"

export const useTrackerState = () => {
	const isLoading = ref(true)
	const step = ref(0)

	const steps = ["Initializing scene", "Loading 3D model", "Setting up MediaPipe", "Starting camera", "Ready!"]

    const progress = computed(() => {
        return (step.value / (steps.length - 1)) * 100
    })

	const setStep = (index: number) => {
		step.value = index
	}

	const nextStep = () => {
		step.value++
	}

	const finishLoading = () => {
		step.value = steps.length - 1
	}

	const setLoaded = () => {
		isLoading.value = false
	}

	return {
		isLoading,
		progress,
		step,
		steps,
		setStep,
		nextStep,
		finishLoading,
		setLoaded,
	}
}
