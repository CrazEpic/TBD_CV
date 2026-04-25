<template>
	<div class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 lg:px-8">
		<section class="grid gap-4 rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/20 backdrop-blur lg:grid-cols-[1.35fr_0.9fr]">
			<div class="space-y-4">
				<div class="space-y-2">
					<p class="text-xs uppercase tracking-[0.35em] text-amber-200/80">Violins and VTubers</p>
					<h1 class="text-4xl font-semibold text-white md:text-5xl">Build a tracking session</h1>
					<p class="max-w-2xl text-sm leading-6 text-slate-300">
						Choose a VRM, pick webcam or video input, then decide whether you want live metrics or a timeline-based evaluation pass.
					</p>
				</div>

				<div class="grid gap-4 md:grid-cols-2">
					<div class="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
						<div class="mb-3 flex items-center justify-between">
							<div>
								<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Model</p>
								<h2 class="text-lg font-medium text-white">Select a VRM</h2>
							</div>
							<span class="text-xs text-slate-400">Built-in or custom</span>
						</div>

						<div class="grid gap-3 sm:grid-cols-3">
							<button
								v-for="character in characters"
								:key="character.id"
								type="button"
								class="group overflow-hidden rounded-2xl border text-left transition"
								:class="activeCharacterId === character.id ? 'border-amber-300 bg-amber-300/15 ring-2 ring-amber-300/70 shadow-lg shadow-amber-300/10' : 'border-white/10 bg-black/20 hover:border-white/20 hover:-translate-y-0.5'"
								:aria-pressed="activeCharacterId === character.id"
								@click="selectBuiltInCharacter(character)"
							>
								<img :src="character.image" :alt="character.name" class="aspect-square w-full object-cover transition duration-300 group-hover:scale-105" />
								<div class="space-y-1 p-3">
									<p class="text-sm font-medium text-white">{{ character.name }}</p>
									<p class="text-xs text-slate-400">{{ character.description }}</p>
								</div>
							</button>
						</div>

						<div class="mt-4 space-y-2">
							<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Custom VRM</p>
							<input class="block w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-200 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-900" type="file" accept=".vrm,.glb,.gltf" @change="onModelFileChange" />
							<p class="text-xs text-slate-400">{{ customModelLabel || 'No custom model selected yet' }}</p>
						</div>
					</div>

					<div class="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
						<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Session</p>
						<div class="mt-2 space-y-3">
							<div>
								<p class="mb-2 text-sm font-medium text-white">Input mode</p>
								<URadioGroup
									v-model="inputModeModel"
									:items="inputModeItems"
									color="primary"
									variant="card"
									orientation="horizontal"
									size="sm"
									class="w-full"
								/>
							</div>

							<div v-if="inputMode === 'video'" class="space-y-2">
								<p class="text-sm font-medium text-white">Source video</p>
								<input class="block w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-200 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-900" type="file" accept="video/*" @change="onVideoFileChange" />
								<p class="text-xs text-slate-400">{{ sourceVideoLabel || 'No video selected yet' }}</p>
							</div>

							<div>
								<p class="mb-2 text-sm font-medium text-white">Evaluation mode</p>
								<URadioGroup
									v-model="evaluationModeModel"
									:items="evaluationModeItems"
									color="primary"
									variant="card"
									orientation="horizontal"
									size="sm"
									class="w-full"
								/>
							</div>
						</div>
					</div>
				</div>
			</div>

			<div class="space-y-4">
				<div v-if="showLabelingEditor" class="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
					<NoteTargetEditor context="labeling" />
				</div>

				<div v-else class="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
					<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Session notes</p>
					<p class="mt-2">
						{{ inputMode === 'webcam' && evaluationMode === 'evaluation' ? 'The note editor will appear during the live session.' : 'Enable video + evaluation to label note timing before starting.' }}
					</p>
				</div>

				<div class="rounded-xl border border-white/10 bg-black/30 p-3 text-sm text-slate-300">
					<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Ready state</p>
					<p class="mt-1">{{ readySummary }}</p>
				</div>

				<div class="flex items-center justify-end">
					<UButton size="lg" :disabled="!canStartSession" @click="$emit('start')">Start session</UButton>
				</div>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import NoteTargetEditor from '~/components/NoteTargetEditor.vue'
import { useTrackerSession } from '~/composables/useTrackerSession'

defineEmits<{ start: [] }>()

const session = useTrackerSession()

const characters = [
	{
		id: 'sample-a',
		name: 'Sample A',
		description: 'A lightweight neutral avatar for testing.',
		image: '/Avatar_SampleA.png',
		model: '/Avatar_SampleA.vrm',
	},
	{
		id: 'sample-b',
		name: 'Sample B',
		description: 'The default reference avatar used in previews.',
		image: '/Avatar_SampleB.png',
		model: '/Avatar_SampleB.vrm',
	},
	{
		id: 'sample-c',
		name: 'Sample C',
		description: 'A third option for comparison sessions.',
		image: '/Avatar_SampleC.png',
		model: '/Avatar_SampleC.vrm',
	},
]

const inputModeItems = [
	{ label: 'Webcam', value: 'webcam', description: 'Use live camera input' },
	{ label: 'Video', value: 'video', description: 'Use uploaded video input' },
]

const evaluationModeItems = [
	{ label: 'No evaluation', value: 'none', description: 'Track without labeling notes' },
	{ label: 'Evaluation mode', value: 'evaluation', description: 'Enable note selection and metrics' },
]

const activeCharacterId = computed(() => session.selectedCharacter.value?.id ?? null)
const hasModelSelection = computed(() => session.hasModelSelection.value)
const inputMode = computed(() => session.inputMode.value)
const evaluationMode = computed(() => session.evaluationMode.value)
const showLabelingEditor = computed(() => inputMode.value === 'video' && evaluationMode.value === 'evaluation')
const canStartSession = computed(() => {
	if (!hasModelSelection.value) return false
	if (inputMode.value === 'video') {
		return Boolean(session.activeSourceVideoUrl.value)
	}
	return true
})
const customModelLabel = computed(() => session.customModelName.value)
const sourceVideoLabel = computed(() => session.sourceVideoName.value)

const inputModeModel = computed({
	get: () => session.inputMode.value,
	set: (value) => session.setSourceMode(value),
})

const evaluationModeModel = computed({
	get: () => session.evaluationMode.value,
	set: (value) => session.setEvaluationMode(value),
})

const readySummary = computed(() => {
	const model = session.activeModelLabel.value ?? 'No model'
	const source = session.inputMode.value === 'video' ? sourceVideoLabel.value ?? 'Video not selected' : 'Webcam'
	const evaluation = session.evaluationMode.value === 'evaluation' ? session.selectedNote.value?.label ?? 'Evaluation enabled' : 'No evaluation'
	return `${model} · ${source} · ${evaluation}`
})

const selectBuiltInCharacter = (character: (typeof characters)[number]) => {
	session.selectBuiltInCharacter({
		id: character.id,
		name: character.name,
		description: character.description,
		image: character.image,
		model: character.model,
	})
}

const onModelFileChange = (event: Event) => {
	const input = event.target as HTMLInputElement
	session.setCustomModel(input.files?.[0] ?? null)
	input.value = ''
}

const onVideoFileChange = (event: Event) => {
	const input = event.target as HTMLInputElement
	session.setSourceVideo(input.files?.[0] ?? null)
	input.value = ''
}
</script>