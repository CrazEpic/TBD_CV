<template>
	<div class="relative h-screen w-full overflow-hidden bg-[#05070d]">
		<!-- THREE RENDERER -->
		<div ref="rendererHost" class="h-full w-full" />

		<div class="absolute left-4 top-4 z-50 flex flex-wrap gap-2 rounded-full border border-white/10 bg-black/55 px-3 py-2 text-[11px] text-slate-200 backdrop-blur">
			<span class="rounded-full bg-white/10 px-2 py-1 uppercase tracking-[0.25em]">{{ props.inputMode }}</span>
			<span class="rounded-full bg-white/10 px-2 py-1 uppercase tracking-[0.25em]">{{ props.evaluationMode }}</span>
			<span class="rounded-full bg-white/10 px-2 py-1 uppercase tracking-[0.25em]">{{ props.modelPath.split('/').pop() }}</span>
		</div>

		<NoteTargetEditor
			v-if="props.inputMode === 'webcam' && props.evaluationMode === 'evaluation'"
			context="live"
			class="absolute left-4 bottom-4 z-50 w-md max-h-[70vh] overflow-auto backdrop-blur"
		/>

<!-- DEBUG CONTROLS -->
	<div class="absolute top-4 right-4 z-50 flex gap-2">
		<UButton
			:icon="showBoneAxes ? 'i-lucide-check' : 'i-lucide-plus'"
			:color="showBoneAxes ? 'success' : 'neutral'"
			variant="outline"
			@click="toggleBoneAxes"
		>
			Axes
		</UButton>
		<UButton
			:icon="showWireframe ? 'i-lucide-check' : 'i-lucide-plus'"
			:color="showWireframe ? 'success' : 'neutral'"
			variant="outline"
			@click="toggleWireframe"
		>
			Wireframe
		</UButton>
		<UButton :icon="showCalibration ? 'i-lucide-sliders-horizontal' : 'i-lucide-sliders'" variant="outline" @click="toggleCalibration">
			Calibration
		</UButton>
			<UButton icon="i-lucide-log-out" color="error" variant="outline" @click="$emit('quit')"> Quit </UButton>
		</div>

		<div
			v-if="showCalibration"
			class="absolute top-16 right-4 z-50 w-96 max-h-[70vh] overflow-auto rounded-lg border border-white/10 bg-black/75 p-4 shadow-lg backdrop-blur"
		>
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-white">Prop Calibration</h3>
				<UButton size="xs" variant="outline" @click="syncCalibration">Reload</UButton>
			</div>

			<div class="mb-3 grid grid-cols-2 gap-2">
				<UButton :color="selectedProp === 'violin' ? 'primary' : 'neutral'" size="xs" variant="outline" @click="selectedProp = 'violin'">
					Violin
				</UButton>
				<UButton :color="selectedProp === 'bow' ? 'primary' : 'neutral'" size="xs" variant="outline" @click="selectedProp = 'bow'">
					Bow
				</UButton>
			</div>

			<div v-if="calibration" class="space-y-3 text-xs text-gray-200">
				<div class="rounded border border-white/10 p-2">
					<div class="mb-2 font-medium text-white">Position</div>
					<div v-for="axis in axes" :key="`p-${axis}`" class="mb-2">
						<div class="mb-1">{{ axis.toUpperCase() }}</div>
						<input
							type="number"
							min="-3"
							max="3"
							step="0.001"
							class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px]"
							:value="getTransformValue('position', axis)"
							@input="setTransformValue('position', axis, Number(($event.target as HTMLInputElement).value))"
						/>
					</div>
				</div>

				<div class="rounded border border-white/10 p-2">
					<div class="mb-2 font-medium text-white">Rotation (deg)</div>
					<div v-for="axis in axes" :key="`r-${axis}`" class="mb-2">
						<div class="mb-1">{{ axis.toUpperCase() }}</div>
						<input
							type="number"
							min="-180"
							max="180"
							step="0.1"
							class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px]"
							:value="getTransformValue('rotationDeg', axis)"
							@input="setTransformValue('rotationDeg', axis, Number(($event.target as HTMLInputElement).value))"
						/>
					</div>
				</div>

				<div class="rounded border border-white/10 p-2">
					<div class="mb-2 font-medium text-white">Scale</div>
					<div v-for="axis in axes" :key="`s-${axis}`" class="mb-2">
						<div class="mb-1">{{ axis.toUpperCase() }}</div>
						<input
							type="number"
							min="0.01"
							max="4"
							step="0.001"
							class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px]"
							:value="getTransformValue('scale', axis)"
							@input="setTransformValue('scale', axis, Number(($event.target as HTMLInputElement).value))"
						/>
					</div>
				</div>

				<div class="rounded border border-white/10 p-2">
					<div class="mb-2 font-medium text-white">Parent Defaults (Base Transform)</div>
					<div v-for="axis in axes" :key="`pp-${axis}`" class="mb-2">
						<div class="mb-1">Position {{ axis.toUpperCase() }}</div>
						<input
							type="number"
							min="-3"
							max="3"
							step="0.001"
							class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px]"
							:value="getParentValue('position', axis)"
							@input="setParentValue('position', axis, Number(($event.target as HTMLInputElement).value))"
						/>
					</div>
					<div class="mb-2 grid grid-cols-2 gap-2">
						<UButton size="xs" variant="outline" @click="bakeSelectedToParent">Bake {{ selectedProp }} Calibration To Parent</UButton>
						<UButton size="xs" variant="outline" @click="resetSelectedParent">Reset {{ selectedProp }} Parent</UButton>
					</div>
				</div>

				<div class="rounded border border-white/10 p-2">
					<div class="mb-2 font-medium text-white">Measurement (Z Direction)</div>
					<div class="mb-2 text-[11px] text-gray-300">Current {{ selectedProp }} Z: {{ getSelectedMeasurementCm().toFixed(2) }} cm</div>
					<div class="mb-2 flex gap-2">
						<UButton size="xs" variant="outline" @click="syncCalibration">Measure Now</UButton>
					</div>
					<div class="mb-2 grid grid-cols-[1fr_auto] items-center gap-2">
						<input v-model.number="targetViolinCm" type="number" step="0.1" class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px]" />
						<UButton size="xs" variant="outline" @click="fitViolinToTarget">Fit Violin (cm)</UButton>
					</div>
					<div class="grid grid-cols-[1fr_auto] items-center gap-2">
						<input v-model.number="targetBowCm" type="number" step="0.1" class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px]" />
						<UButton size="xs" variant="outline" @click="fitBowToTarget">Fit Bow (cm)</UButton>
					</div>
				</div>

				<div class="flex items-center justify-between">
					<UButton size="xs" variant="outline" @click="togglePropVisibility">
						{{ getSelectedCalibration()?.visible ? 'Hide' : 'Show' }} {{ selectedProp }}
					</UButton>
					<UButton size="xs" variant="outline" @click="resetSelectedProp">Reset {{ selectedProp }}</UButton>
				</div>

				<div class="rounded border border-white/10 p-2 text-[11px] text-gray-300">
					<div class="font-medium text-white">Detected Branches</div>
					<div>Violin: {{ diagnostics.violin.branchName }} ({{ diagnostics.violin.meshCount }} meshes)</div>
					<div>Bow: {{ diagnostics.bow.branchName }} ({{ diagnostics.bow.meshCount }} meshes)</div>
				</div>

				<div class="rounded border border-white/10 p-2">
					<div class="mb-2 font-medium text-white">Calibration JSON</div>
					<div class="mb-2 flex gap-2">
						<UButton size="xs" variant="outline" @click="exportCalibration">Export</UButton>
						<UButton size="xs" variant="outline" @click="importCalibration">Import</UButton>
					</div>
					<textarea v-model="calibrationJson" rows="8" class="w-full rounded border border-white/20 bg-black/40 p-2 text-[11px] text-gray-100" />
				</div>
			</div>
		</div>

		<!-- LOADING OVERLAY -->
		<Transition name="fade">
			<div v-if="tracker.isLoading.value" class="absolute inset-0 z-40 flex items-center justify-center bg-black/80 backdrop-blur">
				<UCard class="w-105 space-y-6 p-6">
					<div class="space-y-1 text-center">
						<h1 class="text-xl font-semibold text-white">Loading VRM Tracker</h1>
						<p class="text-sm text-gray-400">
							{{ tracker.steps[tracker.step.value] }}
						</p>
					</div>

					<!-- PROGRESS -->
					<UProgress :value="tracker.progress.value" />

					<p class="text-center text-xs text-gray-400">{{ tracker.progress.value }}%</p>

					<!-- STEP LIST -->
					<div class="space-y-2">
						<div
							v-for="(step, i) in tracker.steps"
							:key="i"
							class="flex items-center gap-3 rounded-md px-3 py-2 transition"
							:class="{
								'bg-primary/10 text-primary border-primary border-l-2': i === tracker.step.value,
								'opacity-50': i < tracker.step.value,
							}"
						>
							<UIcon
								:name="i < tracker.step.value ? 'i-lucide-check' : i === tracker.step.value ? 'i-lucide-loader' : 'i-lucide-circle'"
								class="h-4 w-4"
								:class="{ 'animate-spin': i === tracker.step.value }"
							/>
							<span class="text-sm">{{ step }}</span>
						</div>
					</div>
				</UCard>
			</div>
		</Transition>

		<!-- CAMERA PREVIEW -->
		<div class="absolute right-4 bottom-4 w-70 overflow-hidden rounded-lg border border-white/10 bg-black shadow-lg">
			<video ref="videoElement" :controls="props.inputMode === 'video'" autoplay playsinline class="w-full" />
			<canvas ref="guideCanvas" class="absolute inset-0 w-full pointer-events-none" />
			<div v-if="props.inputMode === 'video' && !props.sourceVideoUrl" class="absolute inset-x-0 bottom-0 bg-black/70 p-3 text-xs text-slate-300">
				Upload a source video to enable frame-by-frame analysis.
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue"

import { useThreeScene } from "@/composables/useThreeScene"
import { useMediaPipeHolistic } from "@/composables/useMediaPipeHolistic"
import { useTrackerState } from "@/composables/useTrackerState"
import { usePoseStream } from "@/composables/usePoseStream"
import { useVRMRig } from "@/composables/useVRMRig"
import { useTrackerPipeline } from "@/composables/useTrackerPipeline"
import { useRuntimeConfig } from "#app"
import NoteTargetEditor from "@/components/NoteTargetEditor.vue"

const props = withDefaults(
	defineProps<{
		modelPath: string
		inputMode?: "webcam" | "video"
		evaluationMode?: "none" | "evaluation"
		sourceVideoUrl?: string | null
		debugMode?: boolean
		smoothFactor?: number
	}>(),
	{
		inputMode: "webcam",
		evaluationMode: "none",
		sourceVideoUrl: null,
		debugMode: false,
		smoothFactor: 15,
	},
)
defineEmits(["quit"])

const rendererHost = ref()
const videoElement = ref()
const guideCanvas = ref()
const showBoneAxes = ref(false)
const showWireframe = ref(false)
const showCalibration = ref(false)

type PropId = "violin" | "bow"
type Axis = "x" | "y" | "z"
const axes: Axis[] = ["x", "y", "z"]
const selectedProp = ref<PropId>("violin")

const tracker = useTrackerState()
const three = useThreeScene(rendererHost)
const mp = useMediaPipeHolistic(videoElement, guideCanvas)
const pose = usePoseStream()
const pipeline = useTrackerPipeline()

type CalibrationMap = ReturnType<typeof three.getPropCalibration>
type ParentDefaultsMap = ReturnType<typeof three.getPropParentDefaults>
type PropMeasurement = NonNullable<ReturnType<typeof three.getPropMeasurement>>
const calibration = ref<CalibrationMap | null>(null)
const parentDefaults = ref<ParentDefaultsMap | null>(null)
const calibrationJson = ref("")
const diagnostics = ref(three.getPropDiagnostics())
const measurements = ref<Record<PropId, PropMeasurement | null>>({ violin: null, bow: null })
const targetViolinCm = ref(57.5)
const targetBowCm = ref(64)

let vrmRig: any = null

let vrm: any = null

pipeline.registerStage("pose-state", (frame) => {
	pose.update(frame.results)
	return frame
})

pipeline.registerStage("vrm-rig", (frame) => {
	vrmRig?.update(frame.results)
	return frame
})

const toggleBoneAxes = () => {
	showBoneAxes.value = !showBoneAxes.value
	vrmRig?.setShowBoneAxes(showBoneAxes.value)
}

const toggleWireframe = () => {
	showWireframe.value = !showWireframe.value
	three.setWireframeMode(showWireframe.value)
}

const toggleCalibration = () => {
	showCalibration.value = !showCalibration.value
	if (showCalibration.value) {
		syncCalibration()
	}
}

const syncCalibration = () => {
	calibration.value = three.getPropCalibration()
	parentDefaults.value = three.getPropParentDefaults()
	diagnostics.value = three.getPropDiagnostics()
	measurements.value = {
		violin: three.getPropMeasurement("violin"),
		bow: three.getPropMeasurement("bow"),
	}
}

const getSelectedCalibration = () => {
	return calibration.value?.[selectedProp.value] ?? null
}

const getTransformValue = (section: "position" | "rotationDeg" | "scale", axis: Axis) => {
	return getSelectedCalibration()?.[section][axis] ?? 0
}

const getParentValue = (section: "position" | "rotationDeg" | "scale", axis: Axis) => {
	return parentDefaults.value?.[selectedProp.value]?.[section][axis] ?? 0
}

const setParentValue = (section: "position" | "rotationDeg" | "scale", axis: Axis, value: number) => {
	if (!parentDefaults.value) return
	const next = parentDefaults.value[selectedProp.value]
	next[section][axis] = value
	three.setPropParentDefaults(selectedProp.value, next)
	syncCalibration()
}

const getSelectedMeasurementCm = () => {
	return measurements.value[selectedProp.value]?.zCm ?? 0
}

const setTransformValue = (section: "position" | "rotationDeg" | "scale", axis: Axis, value: number) => {
	if (!calibration.value) return
	const next = calibration.value[selectedProp.value]
	next[section][axis] = value
	three.setPropCalibration(selectedProp.value, next)
	syncCalibration()
}

const togglePropVisibility = () => {
	const current = getSelectedCalibration()
	if (!current) return
	three.setPropCalibration(selectedProp.value, { visible: !current.visible })
	syncCalibration()
}

const resetSelectedProp = () => {
	three.resetPropCalibration(selectedProp.value)
	syncCalibration()
}

const resetSelectedParent = () => {
	three.resetPropParentDefaults(selectedProp.value)
	syncCalibration()
}

const bakeSelectedToParent = () => {
	three.bakeCalibrationIntoParentDefaults(selectedProp.value)
	syncCalibration()
}

const fitViolinToTarget = () => {
	three.fitPropZLengthCm("violin", targetViolinCm.value)
	syncCalibration()
}

const fitBowToTarget = () => {
	three.fitPropZLengthCm("bow", targetBowCm.value)
	syncCalibration()
}

const exportCalibration = () => {
	calibrationJson.value = three.exportPropCalibration()
}

const importCalibration = () => {
	if (!calibrationJson.value.trim()) return
	try {
		three.importPropCalibration(calibrationJson.value)
		syncCalibration()
	} catch (error) {
		console.error("Invalid calibration JSON", error)
	}
}

onMounted(async () => {
	const config = useRuntimeConfig()
	const base = config.app.baseURL || "/"

	// 1. Scene
	tracker.setStep(0)
	await three.init()
	syncCalibration()

	// 2. VRM
	tracker.setStep(1)
	// Use blob URLs directly, otherwise prepend base for public folder assets
	const modelUrl = props.modelPath.startsWith("blob:") || props.modelPath.startsWith("http")
		? props.modelPath
		: `${base}${props.modelPath}`
	vrm = await three.loadVRM(modelUrl)

	vrmRig = useVRMRig(vrm, {
		debugMode: props.debugMode,
		smoothFactor: props.smoothFactor,
		showBoneAxes: showBoneAxes.value,
	})

	// 3. MediaPipe
	tracker.setStep(2)
	await mp.init(base)

	mp.setOnResults((results) => {
			void pipeline.process({
				results,
				timestamp: performance.now(),
			source: props.inputMode ?? "webcam",
			})
	})

	// 4. Camera
	tracker.setStep(3)
	if (props.inputMode === "video" && props.sourceVideoUrl && videoElement.value) {
		// Use blob URLs directly, otherwise prepend base for public folder assets
		const videoUrl = props.sourceVideoUrl.startsWith("blob:") || props.sourceVideoUrl.startsWith("http")
			? props.sourceVideoUrl
			: `${base}${props.sourceVideoUrl}`
		videoElement.value.src = videoUrl
	}
	await mp.start(props.inputMode)

	tracker.setStep(4)

	setTimeout(() => tracker.setLoaded(), 500)
})

onUnmounted(() => {
	three.dispose()
	mp.stop()
})
</script>
