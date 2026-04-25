<template>
	<div class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 lg:px-8">
		<section class="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/20 backdrop-blur">
			<div class="space-y-2">
				<p class="text-xs tracking-[0.35em] text-amber-200/80 uppercase">Violins and VTubers</p>
				<h1 class="text-4xl font-semibold text-white md:text-5xl">Build a tracking session</h1>
				<p class="max-w-2xl text-sm leading-6 text-slate-300">Step through setup vertically. Completed steps keep a compact preview so you can quickly review your choices.</p>
			</div>

			<div class="mt-6">
				<div class="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
					<div class="rounded-xl border border-white/10 bg-slate-950/40 p-3">
						<p class="text-[11px] tracking-[0.2em] text-slate-400 uppercase">Avatar</p>
						<div class="mt-2 flex items-center gap-3">
							<img v-if="selectedCharacterImage" :src="selectedCharacterImage" alt="Selected avatar" class="h-10 w-10 rounded-lg border border-white/10 object-cover" />
							<div v-else class="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-black/30 text-slate-400">
								<UIcon name="i-lucide-user-round" class="h-4 w-4" />
							</div>
							<p class="text-xs text-slate-200">{{ step1Preview }}</p>
						</div>
					</div>

					<div class="rounded-xl border border-white/10 bg-slate-950/40 p-3">
						<p class="text-[11px] tracking-[0.2em] text-slate-400 uppercase">Input</p>
						<p class="mt-2 text-xs text-slate-200">{{ step2Preview }}</p>
					</div>

					<div class="rounded-xl border border-white/10 bg-slate-950/40 p-3">
						<p class="text-[11px] tracking-[0.2em] text-slate-400 uppercase">Evaluation</p>
						<p class="mt-2 text-xs text-slate-200">{{ step3Preview }}</p>
					</div>

					<div class="rounded-xl border border-white/10 bg-slate-950/40 p-3">
						<p class="text-[11px] tracking-[0.2em] text-slate-400 uppercase">Video</p>
						<div class="mt-2 flex items-center gap-3">
							<video
								v-if="requiresVideoLabeling && sourceVideoUrl"
								:key="`${sourceVideoUrl}-preview-strip`"
								:src="sourceVideoUrl"
								muted
								playsinline
								preload="metadata"
								class="h-10 w-16 rounded-lg border border-white/10 bg-black/40 object-cover"
							/>
							<p class="text-xs text-slate-200">{{ step4Preview }}</p>
						</div>
					</div>
				</div>

				<UStepper v-model="displayStep" :items="stepperItems" orientation="vertical" color="neutral" class="w-full">
					<template #description="{ item }">
						<div class="space-y-2">
							<p class="text-xs text-slate-400">{{ item.description }}</p>
							<img
								v-if="Number(item.value) === 0 && selectedCharacterImage"
								:src="selectedCharacterImage"
								alt="Selected avatar"
								class="h-12 w-12 rounded-lg border border-white/10 object-cover"
							/>
							<video
								v-if="Number(item.value) === 1 && inputMode === 'video' && sourceVideoUrl"
								:key="sourceVideoUrl"
								:src="sourceVideoUrl"
								muted
								playsinline
								preload="metadata"
								class="h-12 w-20 rounded-lg border border-white/10 bg-black/40 object-cover"
							/>
						</div>
					</template>

					<template #model>
						<div :ref="(el) => setStepContentRef(el, 0)" class="mt-3 space-y-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
							<div class="grid gap-3 sm:grid-cols-3">
								<UButton
									v-for="character in characters"
									:key="character.id"
									type="button"
									variant="ghost"
									color="neutral"
									class="group h-auto w-full flex-col items-stretch gap-0 overflow-hidden rounded-2xl border p-0 text-left transition"
									:class="
										activeCharacterId === character.id
											? 'border-amber-300 bg-amber-300/15 shadow-lg ring-2 shadow-amber-300/10 ring-amber-300/70'
											: 'border-white/10 bg-black/20 hover:-translate-y-0.5 hover:border-white/20'
									"
									:aria-pressed="activeCharacterId === character.id"
									@click="selectBuiltInCharacter(character)"
								>
									<img :src="character.image" :alt="character.name" class="aspect-square w-full object-cover transition duration-300 group-hover:scale-105" />
									<div class="space-y-1 p-3">
										<p class="text-sm font-medium text-white">{{ character.name }}</p>
									</div>
								</UButton>
							</div>

							<div class="space-y-2">
								<p class="text-xs tracking-[0.3em] text-slate-400 uppercase">Custom VRM</p>
								<UFileUpload
									v-model="customModelUpload"
									accept=".vrm,.glb,.gltf"
									label="Drop a custom model"
									description="or click to browse"
									color="neutral"
									:preview="false"
									class="w-full"
									@update:model-value="onModelUploadChange"
								/>
							</div>
						</div>
					</template>

					<template #input>
						<div :ref="(el) => setStepContentRef(el, 1)" class="mt-3 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
							<div class="space-y-4">
								<URadioGroup v-model="inputModeSelection" :items="inputModeItems" color="primary" variant="card" orientation="horizontal" size="sm" class="w-full" />

								<div v-if="inputModeSelection === 'video'" class="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
									<div class="space-y-1">
										<p class="text-sm font-medium text-white">Source video</p>
										<p class="text-xs text-slate-400">Pick the video you want to use for tracking before moving on.</p>
									</div>
									<UFileUpload
										v-model="sourceVideoUpload"
										accept="video/*"
										label="Drop a source video"
										description="or click to browse"
										color="neutral"
										:preview="false"
										class="w-full"
										@update:model-value="onVideoUploadChange"
									/>
									<p class="text-xs text-slate-400">{{ sourceVideoLabel || "No video selected yet" }}</p>
									<video v-if="sourceVideoUrl" :key="sourceVideoUrl" :src="sourceVideoUrl" controls class="w-full rounded-xl border border-white/10 bg-black/40" />
								</div>
							</div>
						</div>
					</template>

					<template #evaluation>
						<div :ref="(el) => setStepContentRef(el, 2)" class="mt-3 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
							<URadioGroup v-model="evaluationModeSelection" :items="evaluationModeItems" color="primary" variant="card" orientation="horizontal" size="sm" class="w-full" />
						</div>
					</template>

					<template #labeling>
						<div :ref="(el) => setStepContentRef(el, labelingStepValue)" class="mt-3 space-y-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
							<div class="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
								<p class="text-xs tracking-[0.3em] text-slate-400 uppercase">Labeling preview</p>
								<p class="mt-2 text-sm text-slate-200">{{ sourceVideoLabel || "Use the video selected in the input step." }}</p>
								<NoteTargetEditor context="labeling" />
							</div>
						</div>
					</template>

					<template #start>
						<div :ref="(el) => setStepContentRef(el, startStepValue)" class="mt-3 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
							<div class="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/30 p-3 text-sm text-slate-300">
								<p>{{ requiresVideoLabeling && !sourceVideoUrl ? "Upload a source video to continue." : "Ready to enter tracking session." }}</p>
								<UButton size="lg" :disabled="!canStartSession" @click="startSession">Start session</UButton>
							</div>
						</div>
					</template>
				</UStepper>

				<div class="mt-4 flex items-center justify-between gap-3">
					<UButton variant="outline" color="neutral" size="sm" leading-icon="i-lucide-arrow-left" :disabled="!hasPrevStep" @click="goToPrevStep"> Back </UButton>
					<UButton variant="outline" color="neutral" size="sm" trailing-icon="i-lucide-arrow-right" :disabled="!hasNextStep" @click="goToNextStep"> Next </UButton>
				</div>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, type ComponentPublicInstance } from "vue"
import type { StepperItem } from "@nuxt/ui"
import NoteTargetEditor from "~/components/NoteTargetEditor.vue"
import { useTrackerSession } from "~/composables/useTrackerSession"

const emit = defineEmits<{ start: [] }>()

const session = useTrackerSession()
const customModelUpload = ref<File | null>(null)
const sourceVideoUpload = ref<File | null>(null)
const inputModeSelection = ref<"webcam" | "video" | undefined>(undefined)
const evaluationModeSelection = ref<"none" | "evaluation" | undefined>(undefined)
const stepContentRefs = new Map<number, HTMLElement>()

const characters = [
	{
		id: "sample-a",
		name: "Sample A",
		description: "Default balanced avatar",
		image: "/Avatar_SampleA.png",
		model: "/Avatar_SampleA.vrm",
	},
	{
		id: "sample-b",
		name: "Sample B",
		description: "Alternative expression preset",
		image: "/Avatar_SampleB.png",
		model: "/Avatar_SampleB.vrm",
	},
	{
		id: "sample-c",
		name: "Sample C",
		description: "High-contrast stylized avatar",
		image: "/Avatar_SampleC.png",
		model: "/Avatar_SampleC.vrm",
	},
]

const inputModeItems = [
	{ label: "Webcam", value: "webcam", description: "Use live camera input" },
	{ label: "Video", value: "video", description: "Use uploaded video input" },
]

const evaluationModeItems = [
	{ label: "No evaluation", value: "none", description: "Track without labeling notes" },
	{ label: "Evaluation mode", value: "evaluation", description: "Enable note selection and metrics" },
]

const activeCharacterId = computed(() => session.selectedCharacter.value?.id ?? null)
const hasModelSelection = computed(() => session.hasModelSelection.value)
const inputMode = computed(() => inputModeSelection.value)
const evaluationMode = computed(() => evaluationModeSelection.value)
const sourceVideoUrl = computed(() => session.activeSourceVideoUrl.value)
const requiresVideoLabeling = computed(() => inputMode.value === "video" && evaluationMode.value === "evaluation")
const isStep1Done = computed(() => hasModelSelection.value)
const isStep2Done = computed(() => inputMode.value !== undefined)
const isStep3Done = computed(() => evaluationMode.value !== undefined)
const isReadyForStartStep = computed(() => (requiresVideoLabeling.value ? Boolean(sourceVideoUrl.value) : true))
const labelingStepValue = 3
const startStepValue = computed(() => (requiresVideoLabeling.value ? 4 : 3))

const displayStep = ref(0)
const selectedCharacterImage = computed(() => session.selectedCharacter.value?.image ?? null)
const sourceVideoLabel = computed(() => session.sourceVideoName.value)
const step1Preview = computed(() => session.activeModelLabel.value ?? "Choose a built-in or custom VRM")
const step2Preview = computed(() => {
	if (inputMode.value === undefined) return "Not selected yet"
	return inputMode.value === "video" ? "Video input" : "Webcam input"
})
const step3Preview = computed(() => {
	if (evaluationMode.value === undefined) return "Not selected yet"
	return evaluationMode.value === "evaluation" ? "Evaluation mode enabled" : "No evaluation"
})
const step4Preview = computed(() => sourceVideoLabel.value ?? "Upload a source video to label timeline")
const readySummary = computed(() => {
	const model = session.activeModelLabel.value ?? "No model"
	const source = inputMode.value === "video" ? (sourceVideoLabel.value ?? "Video not selected") : inputMode.value === "webcam" ? "Webcam" : "Input mode pending"
	const evaluation =
		evaluationMode.value === "evaluation" ? (session.selectedNote.value?.label ?? "Evaluation enabled") : evaluationMode.value === "none" ? "No evaluation" : "Evaluation mode pending"
	return `${model} · ${source} · ${evaluation}`
})
const enabledStepValues = computed(() => stepperItems.value.filter((item) => !item.disabled).map((item) => Number(item.value)))
const currentStepIndex = computed(() => enabledStepValues.value.findIndex((value) => value === displayStep.value))
const hasPrevStep = computed(() => currentStepIndex.value > 0)
const hasNextStep = computed(() => currentStepIndex.value >= 0 && currentStepIndex.value < enabledStepValues.value.length - 1)

const stepperItems = computed<StepperItem[]>(() => {
	const items: StepperItem[] = [
		{ title: "Select a VRM", description: step1Preview.value, icon: "i-lucide-user-round", value: 0, slot: "model" },
		{ title: "Select input mode", description: step2Preview.value, icon: "i-lucide-video", value: 1, slot: "input", disabled: !isStep1Done.value },
		{ title: "Select evaluation mode", description: step3Preview.value, icon: "i-lucide-list-checks", value: 2, slot: "evaluation", disabled: !isStep2Done.value },
	]

	if (requiresVideoLabeling.value) {
		items.push({ title: "Label video timeline", description: step4Preview.value, icon: "i-lucide-clapperboard", value: labelingStepValue, slot: "labeling", disabled: !isStep3Done.value })
	}

	items.push({ title: "Start session", description: readySummary.value, icon: "i-lucide-play", value: startStepValue.value, slot: "start", disabled: !isReadyForStartStep.value })
	return items
})

const setStepContentRef = (el: Element | ComponentPublicInstance | null, step: number) => {
	if (!el) {
		stepContentRefs.delete(step)
		return
	}

	const maybeElement = "$el" in (el as ComponentPublicInstance) ? ((el as ComponentPublicInstance).$el as Element | null) : (el as Element)
	if (maybeElement instanceof HTMLElement) {
		stepContentRefs.set(step, maybeElement)
	}
}

const scrollToStep = async (step: number) => {
	await nextTick()
	stepContentRefs.get(step)?.scrollIntoView({ behavior: "smooth", block: "start" })
}

watch(enabledStepValues, (values) => {
	if (!values.length) {
		displayStep.value = 0
		return
	}

	if (!values.includes(displayStep.value)) {
		displayStep.value = values[values.length - 1] as number
	}
})

watch(displayStep, (step) => {
	void scrollToStep(step)
})

const goToPrevStep = () => {
	if (!hasPrevStep.value) return
	displayStep.value = enabledStepValues.value[currentStepIndex.value - 1] as number
}

const goToNextStep = () => {
	if (!hasNextStep.value) return
	displayStep.value = enabledStepValues.value[currentStepIndex.value + 1] as number
}

const canStartSession = computed(() => {
	if (!hasModelSelection.value) return false
	if (!inputMode.value) return false
	if (!evaluationMode.value) return false
	if (inputMode.value === "video") {
		return Boolean(session.activeSourceVideoUrl.value)
	}
	return true
})
const customModelLabel = computed(() => session.customModelName.value)

const startSession = () => {
	if (!inputModeSelection.value || !evaluationModeSelection.value) {
		return
	}

	session.setSourceMode(inputModeSelection.value)
	session.setEvaluationMode(evaluationModeSelection.value)
	if (!canStartSession.value) {
		return
	}

	emit("start")
}

const selectBuiltInCharacter = (character: (typeof characters)[number]) => {
	customModelUpload.value = null
	session.selectBuiltInCharacter({
		id: character.id,
		name: character.name,
		description: character.description,
		image: character.image,
		model: character.model,
	})
}

const onModelUploadChange = (value: File | null | undefined) => {
	const file = value ?? null
	customModelUpload.value = file
	session.setCustomModel(file)
}

const onVideoUploadChange = (value: File | null | undefined) => {
	const file = value ?? null
	sourceVideoUpload.value = file
	session.setSourceVideo(file)
}
</script>
