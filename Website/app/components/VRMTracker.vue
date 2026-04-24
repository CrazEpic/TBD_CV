<template>
	<div class="relative h-screen w-full overflow-hidden bg-[#05070d]">
		<!-- THREE RENDERER -->
		<div ref="rendererHost" class="h-full w-full" />

		<!-- QUIT BUTTON -->
		<div class="absolute top-4 right-4 z-50">
			<UButton icon="i-lucide-log-out" color="red" variant="outline" @click="$emit('quit')"> Quit </UButton>
		</div>

		<!-- LOADING OVERLAY -->
		<Transition name="fade">
			<div v-if="tracker.isLoading.value" class="absolute inset-0 z-40 flex items-center justify-center bg-black/80 backdrop-blur">
				<UCard class="w-[420px] space-y-6 p-6">
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
		<div class="absolute right-4 bottom-4 w-[280px] overflow-hidden rounded-lg border border-white/10 bg-black shadow-lg">
			<video ref="videoElement" autoplay muted playsinline class="w-full scale-x-[-1]" />
			<canvas ref="guideCanvas" class="absolute inset-0 w-full scale-x-[-1]" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue"

import { useThreeScene } from "@/composables/useThreeScene"
import { useMediaPipeHolistic } from "@/composables/useMediaPipeHolistic"
import { useTrackerState } from "@/composables/useTrackerState"
import { useRuntimeConfig } from "#app"

const props = defineProps<{ modelPath: string }>()
defineEmits(["quit"])

const rendererHost = ref()
const videoElement = ref()
const guideCanvas = ref()

const tracker = useTrackerState()
const three = useThreeScene(rendererHost)
const mp = useMediaPipeHolistic(videoElement)
const pose = usePoseStream()
let vrmRig

let vrm: any = null

onMounted(async () => {
	const config = useRuntimeConfig()
	const base = config.app.baseURL || "/"

	// 1. Scene
	tracker.setStep(0)
	await three.init()

	// 2. VRM
	tracker.setStep(1)
	vrm = await three.loadVRM(`${base}${props.modelPath}`)

	vrmRig = useVRMRig(vrm)

	// 3. MediaPipe
	tracker.setStep(2)
	await mp.init(base)

	mp.setOnResults((results) => {
		pose.update(results)
		// vrmRig.update()
	})

	// 4. Camera
	tracker.setStep(3)
	await mp.start()

	tracker.setStep(4)

	setTimeout(() => tracker.setLoaded(), 500)
})

onUnmounted(() => {
	three.dispose()
	mp.stop()
})
</script>
