import { computed, ref } from "vue"
import { useSelectedCharacter, type Character } from "@/composables/useSelectedCharacter"
import { VIOLIN_NOTE_OPTIONS, type ViolinNoteOption } from "@/utils/violinNotes"

export type InputMode = "webcam" | "video"
export type EvaluationMode = "none" | "evaluation"

export type SessionNoteRange = {
	id: string
	noteId: string
	startMs: number
	endMs: number | null
}

export type TrackerSessionExport = {
	inputMode: InputMode
	evaluationMode: EvaluationMode
	selectedNoteId: string | null
	noteRanges: SessionNoteRange[]
	customModelName: string | null
	sourceVideoName: string | null
	selectedCharacterId: string | null
}

const customModelObjectUrl = ref<string | null>(null)
const sourceVideoObjectUrl = ref<string | null>(null)

const inputMode = ref<InputMode>("webcam")
const evaluationMode = ref<EvaluationMode>("none")
const selectedNoteId = ref<string | null>(null)
const noteRanges = ref<SessionNoteRange[]>([])
const customModelName = ref<string | null>(null)
const sourceVideoName = ref<string | null>(null)
const sourceVideoDurationMs = ref<number | null>(null)

export const useTrackerSession = () => {
	const { selectedCharacter, setCharacter, clearCharacter } = useSelectedCharacter()

	const activeModelPath = computed(() => customModelObjectUrl.value ?? selectedCharacter.value?.model ?? null)
	const activeModelLabel = computed(() => customModelName.value ?? selectedCharacter.value?.name ?? null)
	const activeSourceVideoUrl = computed(() => sourceVideoObjectUrl.value)
	const hasModelSelection = computed(() => Boolean(activeModelPath.value))
	const selectedNote = computed<ViolinNoteOption | null>(() => {
		return VIOLIN_NOTE_OPTIONS.find((option) => option.id === selectedNoteId.value) ?? null
	})

	const setSourceMode = (mode: InputMode) => {
		inputMode.value = mode
	}

	const setEvaluationMode = (mode: EvaluationMode) => {
		evaluationMode.value = mode
		if (mode === "none") {
			selectedNoteId.value = null
		}
	}

	const selectBuiltInCharacter = (character: Character) => {
		if (customModelObjectUrl.value) {
			URL.revokeObjectURL(customModelObjectUrl.value)
			customModelObjectUrl.value = null
		}
		customModelName.value = null
		setCharacter(character)
	}

	const setCustomModel = (file: File | null) => {
		if (customModelObjectUrl.value) {
			URL.revokeObjectURL(customModelObjectUrl.value)
			customModelObjectUrl.value = null
		}

		if (!file) {
			customModelName.value = null
			clearCharacter()
			return
		}

		customModelObjectUrl.value = URL.createObjectURL(file)
		customModelName.value = file.name
		clearCharacter()
	}

	const setSourceVideo = (file: File | null) => {
		if (sourceVideoObjectUrl.value) {
			URL.revokeObjectURL(sourceVideoObjectUrl.value)
			sourceVideoObjectUrl.value = null
		}

		if (!file) {
			sourceVideoName.value = null
			sourceVideoDurationMs.value = null
			return
		}

		sourceVideoObjectUrl.value = URL.createObjectURL(file)
		sourceVideoName.value = file.name
		sourceVideoDurationMs.value = null

		if (import.meta.client) {
			const probe = document.createElement("video")
			probe.preload = "metadata"
			probe.src = sourceVideoObjectUrl.value

			const finalize = () => {
				probe.removeAttribute("src")
				probe.load()
			}

			probe.onloadedmetadata = () => {
				if (Number.isFinite(probe.duration) && probe.duration > 0) {
					sourceVideoDurationMs.value = Math.round(probe.duration * 1000)
				}
				finalize()
			}

			probe.onerror = () => {
				sourceVideoDurationMs.value = null
				finalize()
			}
		}
	}

	const setSelectedNoteId = (noteId: string | null) => {
		selectedNoteId.value = noteId
	}

		const deleteNoteRange = (rangeId: string) => {
			noteRanges.value = noteRanges.value.filter((range) => range.id !== rangeId)
		}

	const addNoteRange = (range: SessionNoteRange) => {
		noteRanges.value = [...noteRanges.value, range]
	}

	const updateNoteRange = (rangeId: string, patch: Partial<SessionNoteRange>) => {
		noteRanges.value = noteRanges.value.map((range) => (range.id === rangeId ? { ...range, ...patch } : range))
	}

	const clearNoteRanges = () => {
		noteRanges.value = []
	}

	const exportSession = (): string => {
		const payload: TrackerSessionExport = {
			inputMode: inputMode.value,
			evaluationMode: evaluationMode.value,
			selectedNoteId: selectedNoteId.value,
			noteRanges: noteRanges.value,
			customModelName: customModelName.value,
			sourceVideoName: sourceVideoName.value,
			selectedCharacterId: selectedCharacter.value?.id ?? null,
		}

		return JSON.stringify(payload, null, 2)
	}

	const exportLabeling = (): string => {
		return JSON.stringify(
			{
				selectedNoteId: selectedNoteId.value,
				noteRanges: noteRanges.value,
			},
			null,
			2,
		)
	}

	const importLabeling = (rawJson: string) => {
		const parsed = JSON.parse(rawJson) as Partial<Pick<TrackerSessionExport, "selectedNoteId" | "noteRanges">>
		selectedNoteId.value = typeof parsed.selectedNoteId === "string" ? parsed.selectedNoteId : null
		noteRanges.value = Array.isArray(parsed.noteRanges) ? parsed.noteRanges : []
	}

	const importSession = (rawJson: string) => {
		const parsed = JSON.parse(rawJson) as Partial<TrackerSessionExport>
		if (parsed.inputMode === "webcam" || parsed.inputMode === "video") {
			inputMode.value = parsed.inputMode
		}
		if (parsed.evaluationMode === "none" || parsed.evaluationMode === "evaluation") {
			evaluationMode.value = parsed.evaluationMode
		}
		selectedNoteId.value = typeof parsed.selectedNoteId === "string" ? parsed.selectedNoteId : null
		noteRanges.value = Array.isArray(parsed.noteRanges) ? parsed.noteRanges : []
		customModelName.value = typeof parsed.customModelName === "string" ? parsed.customModelName : null
		sourceVideoName.value = typeof parsed.sourceVideoName === "string" ? parsed.sourceVideoName : null
	}

	return {
		inputMode,
		evaluationMode,
		selectedNoteId,
		noteRanges,
		customModelName,
		sourceVideoName,
		sourceVideoDurationMs,
		selectedCharacter,
		activeModelPath,
		activeModelLabel,
		activeSourceVideoUrl,
		hasModelSelection,
		selectedNote,
		setSourceMode,
		setEvaluationMode,
		selectBuiltInCharacter,
		setCustomModel,
		setSourceVideo,
		setSelectedNoteId,
		addNoteRange,
		updateNoteRange,
		deleteNoteRange,
		clearNoteRanges,
		exportSession,
		exportLabeling,
		importLabeling,
		importSession,
	}
}