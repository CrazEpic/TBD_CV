<template>
	<div class="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Note target</p>
				<h2 class="text-lg font-medium text-white">Violin positions</h2>
			</div>
			<span class="text-xs text-slate-400">{{ noteOptions.length }} options</span>
		</div>

		<div class="mt-4 rounded-xl border border-white/10 bg-black/30 p-3">
			<div class="mb-2 flex items-center justify-between gap-2">
				<p class="text-xs uppercase tracking-[0.3em] text-slate-400">String note grid</p>
				<p class="text-xs text-slate-400">Selected: {{ selectedNoteLabel || 'None' }}</p>
			</div>
			<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
				<div v-for="column in groupedNoteColumns" :key="column.stringName" class="rounded-lg border border-white/10 bg-slate-950/40 p-2">
					<p class="text-center text-xs font-semibold tracking-[0.2em] text-slate-300">{{ column.stringName }} string</p>
					<div class="mt-2 grid gap-1">
						<UButton
							v-for="note in column.notes"
							:key="note.id"
							size="xs"
							:color="selectedNoteId === note.id ? 'primary' : 'neutral'"
							:variant="selectedNoteId === note.id ? 'solid' : 'outline'"
							class="h-8 w-full justify-center"
							@click="selectedNoteIdModel = note.id"
						>
							{{ note.label }}
						</UButton>
					</div>
				</div>
			</div>
		</div>

		<div v-if="props.context === 'labeling'" class="mt-4 space-y-4">
			<div class="grid gap-3 rounded-xl border border-white/10 bg-black/30 p-4">
				<div v-if="sourceVideoUrl" class="space-y-2 rounded-xl border border-white/10 bg-slate-950/50 p-3">
					<div class="flex items-center justify-between">
						<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Video preview</p>
						<p class="text-xs text-slate-300">{{ formatMs(timelineCursorMs) }}</p>
					</div>
					<video
						ref="previewVideoRef"
						:key="sourceVideoUrl"
						:src="sourceVideoUrl"
						controls
						playsinline
						class="w-full rounded-lg border border-white/10 bg-black"
						@loadedmetadata="onPreviewVideoLoaded"
						@timeupdate="onPreviewVideoTimeUpdate"
						@play="onPreviewVideoPlay"
						@pause="onPreviewVideoPause"
						@seeking="onPreviewVideoTimeUpdate"
						@ended="onPreviewVideoPause"
					/>
				</div>

				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<p class="text-sm font-medium text-white">Labeling timeline</p>
						<p class="text-xs text-slate-400">Move cursor and add segments. Drag Start/End labels in the list to scrub values.</p>
					</div>
					<div class="flex gap-2">
						<UButton size="xs" variant="outline" color="primary" @click="addRangeAtCursor">Add at cursor</UButton>
						<UButton size="xs" variant="outline" color="error" :disabled="!noteRanges.length" @click="session.clearNoteRanges">Clear</UButton>
					</div>
				</div>

				<div class="rounded-xl border border-white/10 bg-slate-950/50 p-3">
					<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
						<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Cursor</p>
						<p class="text-xs text-slate-300">{{ formatMs(timelineCursorMs) }} / {{ formatMs(timelineMaxMs) }}</p>
					</div>
					<USlider v-model="timelineCursorModel" :min="0" :max="timelineMaxMs" :step="10" :tooltip="true" />

					<div class="relative mt-4 h-9 overflow-hidden rounded-lg border border-white/10 bg-black/30">
						<div
							v-for="segment in segmentVisuals"
							:key="segment.id"
							class="absolute top-1 bottom-1 z-10 rounded-md border border-amber-200/70 bg-amber-300/35"
							:style="segment.style"
							:title="segment.tooltip"
						/>
						<div class="absolute inset-y-0 w-0.5 bg-white/80" :style="{ left: `${cursorPercent}%` }" />
					</div>
					<p class="mt-2 text-xs text-slate-400">
						{{ noteRanges.length ? `${noteRanges.length} segment(s) on timeline` : 'No segments yet. Add one at the current cursor position.' }}
					</p>
				</div>

				<div class="grid gap-3 md:grid-cols-[1fr_auto]">
					<div class="rounded-xl border border-white/10 bg-slate-950/50 p-3 text-xs text-slate-300 md:w-56">
						<p class="font-medium text-white">Export / import</p>
						<p class="mt-2">Save or load your labeling data as a JSON file.</p>
						<div class="mt-3 flex flex-col gap-2">
							<UButton size="xs" variant="outline" color="neutral" @click="exportLabeling">Export JSON</UButton>
							<UFileUpload
								v-model="labelingFile"
								accept="application/json,.json"
								label="Import JSON file"
								description="Drop a saved labeling file here or browse"
								color="neutral"
								:preview="false"
								class="w-full"
								@update:model-value="onLabelingFileChange"
							/>
						</div>
					</div>
				</div>

				<div v-if="noteRanges.length" class="space-y-3">
					<div v-for="range in noteRanges" :key="range.id" class="rounded-xl border border-white/10 bg-slate-950/50 p-3">
						<div class="mb-3 flex items-start justify-between gap-2">
							<div>
								<p class="text-sm font-medium text-white">{{ getNoteDisplayLabel(range.noteId) }}</p>
								<p class="text-xs text-slate-400">{{ formatMs(toNumber(range.startMs)) }} to {{ formatMs(getRangeEndMs(range)) }}</p>
							</div>
							<UButton size="xs" color="error" variant="outline" @click.stop="session.deleteNoteRange(range.id)">Delete</UButton>
						</div>

						<div class="grid gap-3 md:grid-cols-[1fr_repeat(2,minmax(0,11rem))]">
							<div class="rounded-xl border border-white/10 bg-black/20 p-3">
								<p class="text-[11px] uppercase tracking-[0.18em] text-slate-400">Selected note</p>
								<p class="mt-1 text-sm text-white">{{ getNoteDisplayLabel(range.noteId) }}</p>
							</div>

							<div class="space-y-1">
								<button type="button" class="cursor-ew-resize text-[11px] uppercase tracking-[0.18em] text-slate-400" @pointerdown.prevent="startValueScrub($event, range.id, 'start')">
									Start (drag)
								</button>
								<UInputNumber
									:min="0"
									:step="10"
									:format-options="{ style: 'decimal' }"
									:model-value="toNumber(range.startMs)"
									placeholder="Start ms"
									@update:model-value="(value) => setRangeStart(range.id, value)"
								/>
							</div>
							<div class="space-y-1">
								<button type="button" class="cursor-ew-resize text-[11px] uppercase tracking-[0.18em] text-slate-400" @pointerdown.prevent="startValueScrub($event, range.id, 'end')">
									End (drag)
								</button>
								<UInputNumber
									:min="0"
									:step="10"
									:format-options="{ style: 'decimal' }"
									:model-value="getRangeEndMs(range)"
									placeholder="End ms"
									@update:model-value="(value) => setRangeEnd(range.id, value)"
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div v-else class="mt-4 rounded-xl border border-white/10 bg-black/30 p-3 text-sm text-slate-300">
			<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Current note</p>
			<p class="mt-1">{{ selectedNoteLabel || 'No note selected' }}</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { VIOLIN_NOTE_OPTIONS, type ViolinNoteOption, type ViolinStringName } from "@/utils/violinNotes"
import { useTrackerSession, type SessionNoteRange } from "@/composables/useTrackerSession"

const props = defineProps<{
	context: "live" | "labeling"
}>()

const session = useTrackerSession()
const noteOptions = VIOLIN_NOTE_OPTIONS
const timelineCursorMs = ref(0)
const previewVideoRef = ref<HTMLVideoElement | null>(null)
const stringOrder: ViolinStringName[] = ["G", "D", "A", "E"]
const sourceVideoUrl = computed(() => session.activeSourceVideoUrl.value)
const isPreviewPlaying = ref(false)
let playbackFrameId = 0
let scrubMoveListener: ((event: PointerEvent) => void) | null = null
let scrubUpListener: ((event: PointerEvent) => void) | null = null

const SCRUB_MS_PER_PIXEL = 20
const SEGMENT_MIN_MS = 10

const selectedNoteId = computed(() => session.selectedNoteId.value)
const selectedNoteLabel = computed(() => session.selectedNote.value?.label ?? null)
const noteRanges = computed(() => session.noteRanges.value)

const groupedNoteColumns = computed(() => {
	return stringOrder.map((stringName) => ({
		stringName,
		notes: noteOptions.filter((note) => note.stringName === stringName).sort((a, b) => a.semitoneOffset - b.semitoneOffset),
	}))
})

const getNoteLabel = (noteId: string) => {
	return noteOptions.find((note) => note.id === noteId)?.label ?? noteId
}

const getNoteDisplayLabel = (noteId: string) => {
	const note = noteOptions.find((n) => n.id === noteId)
	if (!note) return noteId
	return `${note.label} (${note.stringName} string)`
}

const labelingFile = ref<File | null>(null)

const onLabelingFileChange = async (value: File | null | undefined) => {
	const file = value ?? null
	if (!file) return
	try {
		const text = await file.text()
		session.importLabeling(text)
	} catch (e) {
		console.error('Failed to import labeling file:', e)
	}
}

const selectedNoteIdModel = computed({
	get: () => session.selectedNoteId.value ?? undefined,
	set: (value: string | undefined) => session.setSelectedNoteId(value ?? null),
})

const toNumber = (value: unknown, fallback = 0): number => {
	if (typeof value === "number" && Number.isFinite(value)) {
		return value
	}

	const parsed = Number(value)
	return Number.isFinite(parsed) ? parsed : fallback
}

const clamp = (value: number, min: number, max: number) => {
	return Math.min(max, Math.max(min, value))
}

const timelineMaxMs = computed(() => {
	const sourcedDuration = session.sourceVideoDurationMs.value ?? 0
	const rangeMax = session.noteRanges.value.reduce((max, range) => {
		const start = toNumber(range.startMs)
		const end = range.endMs == null ? start + 800 : toNumber(range.endMs, start + 800)
		return Math.max(max, end)
	}, 0)

	return Math.max(sourcedDuration, rangeMax + 1200, 5000)
})

watch(timelineMaxMs, (nextMax) => {
	timelineCursorMs.value = clamp(timelineCursorMs.value, 0, nextMax)
})

const timelineCursorModel = computed({
	get: () => timelineCursorMs.value,
	set: (value: number | number[] | undefined) => {
		const numericValue = Array.isArray(value) ? toNumber(value[0]) : toNumber(value)
		timelineCursorMs.value = clamp(numericValue, 0, timelineMaxMs.value)

		const video = previewVideoRef.value
		if (video) {
			const targetSeconds = timelineCursorMs.value / 1000
			if (Math.abs(video.currentTime - targetSeconds) > 0.03) {
				video.currentTime = targetSeconds
			}
		}
	},
})

const cursorPercent = computed(() => {
	if (!timelineMaxMs.value) {
		return 0
	}

	return (timelineCursorMs.value / timelineMaxMs.value) * 100
})

const formatMs = (ms: number) => {
	const clamped = Math.max(0, Math.round(ms))
	const minutes = Math.floor(clamped / 60000)
	const seconds = Math.floor((clamped % 60000) / 1000)
	const millis = clamped % 1000
	return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(millis).padStart(3, "0")}`
}

const getRangeEndMs = (range: SessionNoteRange) => {
	const start = toNumber(range.startMs)
	const fallback = Math.min(start + 800, timelineMaxMs.value)
	const end = range.endMs == null ? fallback : toNumber(range.endMs, fallback)
	return clamp(Math.max(end, start), 0, timelineMaxMs.value)
}

const segmentVisuals = computed(() => {
	const total = Math.max(1, timelineMaxMs.value)

	return session.noteRanges.value.map((range) => {
		const start = clamp(toNumber(range.startMs), 0, total)
		const end = clamp(Math.max(getRangeEndMs(range), start + 10), 0, total)
		const leftPercent = (start / total) * 100
		const widthPercent = Math.max(((end - start) / total) * 100, 0.6)

		return {
			id: range.id,
			start,
			end,
			style: {
				left: `${leftPercent}%`,
				width: `${widthPercent}%`,
			},
			tooltip: `${range.noteId} | ${formatMs(start)} - ${formatMs(end)}`,
		}
	})
})

const addRangeAtCursor = () => {
	const startMs = Math.round(timelineCursorMs.value)
	const endMs = Math.min(startMs + 1000, timelineMaxMs.value)
	const selectedId = session.selectedNoteId.value ?? noteOptions[0]?.id
	if (!selectedId) return
	session.addNoteRange({
		id: crypto.randomUUID(),
		noteId: selectedId,
		startMs,
		endMs,
	})
}

const exportLabeling = () => {
	const json = session.exportLabeling()
	const blob = new Blob([json], { type: 'application/json' })
	const url = URL.createObjectURL(blob)
	const a = document.createElement('a')
	a.href = url
	a.download = 'labeling.json'
	a.click()
	URL.revokeObjectURL(url)
}

const setRangeStart = (rangeId: string, value: number | string | null | undefined) => {
	const startMs = clamp(toNumber(value), 0, timelineMaxMs.value)
	const range = session.noteRanges.value.find((entry) => entry.id === rangeId)
	const fallbackEnd = Math.min(startMs + 200, timelineMaxMs.value)
	const currentEnd = range ? getRangeEndMs(range) : fallbackEnd

	session.updateNoteRange(rangeId, {
		startMs,
		endMs: Math.max(currentEnd, startMs),
	})
}

const setRangeEnd = (rangeId: string, value: number | string | null | undefined) => {
	const range = session.noteRanges.value.find((entry) => entry.id === rangeId)
	if (!range) return

	const startMs = toNumber(range.startMs)
	const nextEnd = clamp(toNumber(value, startMs), startMs, timelineMaxMs.value)
	session.updateNoteRange(rangeId, { endMs: nextEnd })
}

type ScrubField = "start" | "end" | "length"

const applyScrubDelta = (segmentId: string, field: ScrubField, deltaMs: number) => {
	const range = noteRanges.value.find((entry) => entry.id === segmentId)
	if (!range) return

	const startMs = toNumber(range.startMs)
	const endMs = getRangeEndMs(range)
	const roundedDelta = Math.round(deltaMs / 10) * 10

	if (field === "start") {
		const nextStart = clamp(startMs + roundedDelta, 0, Math.max(0, endMs - SEGMENT_MIN_MS))
		session.updateNoteRange(segmentId, { startMs: nextStart, endMs })
		timelineCursorMs.value = nextStart
		return
	}

	if (field === "end") {
		const nextEnd = clamp(endMs + roundedDelta, startMs + SEGMENT_MIN_MS, timelineMaxMs.value)
		session.updateNoteRange(segmentId, { endMs: nextEnd })
		timelineCursorMs.value = nextEnd
		return
	}

	const nextEnd = clamp(endMs + roundedDelta, startMs + SEGMENT_MIN_MS, timelineMaxMs.value)
	session.updateNoteRange(segmentId, { endMs: nextEnd })
	timelineCursorMs.value = nextEnd
}

const stopScrubListeners = () => {
	if (scrubMoveListener) {
		window.removeEventListener("pointermove", scrubMoveListener)
		scrubMoveListener = null
	}

	if (scrubUpListener) {
		window.removeEventListener("pointerup", scrubUpListener)
		window.removeEventListener("pointercancel", scrubUpListener)
		scrubUpListener = null
	}
}

const startValueScrub = (event: PointerEvent, segmentId: string, field: ScrubField) => {
	const startX = event.clientX
	let previousDelta = 0

	stopScrubListeners()
	scrubMoveListener = (moveEvent: PointerEvent) => {
		const absoluteDelta = (moveEvent.clientX - startX) * SCRUB_MS_PER_PIXEL
		const stepDelta = absoluteDelta - previousDelta
		previousDelta = absoluteDelta
		applyScrubDelta(segmentId, field, stepDelta)
	}

	scrubUpListener = () => {
		stopScrubListeners()
	}

	window.addEventListener("pointermove", scrubMoveListener)
	window.addEventListener("pointerup", scrubUpListener)
	window.addEventListener("pointercancel", scrubUpListener)
}

const syncCursorFromVideo = () => {
	const video = previewVideoRef.value
	if (!video) return
	timelineCursorMs.value = clamp(Math.round(video.currentTime * 1000), 0, timelineMaxMs.value)
}

const stopPlaybackSync = () => {
	isPreviewPlaying.value = false
	if (playbackFrameId) {
		cancelAnimationFrame(playbackFrameId)
		playbackFrameId = 0
	}
}

const playbackSyncTick = () => {
	if (!isPreviewPlaying.value) {
		return
	}

	syncCursorFromVideo()
	playbackFrameId = requestAnimationFrame(playbackSyncTick)
}

const onPreviewVideoLoaded = () => {
	syncCursorFromVideo()
}

const onPreviewVideoTimeUpdate = () => {
	syncCursorFromVideo()
}

const onPreviewVideoPlay = () => {
	isPreviewPlaying.value = true
	if (!playbackFrameId) {
		playbackFrameId = requestAnimationFrame(playbackSyncTick)
	}
}

const onPreviewVideoPause = () => {
	stopPlaybackSync()
	syncCursorFromVideo()
}

watch(sourceVideoUrl, () => {
	stopPlaybackSync()
	timelineCursorMs.value = 0
})

onBeforeUnmount(() => {
	stopPlaybackSync()
	stopScrubListeners()
})
</script>