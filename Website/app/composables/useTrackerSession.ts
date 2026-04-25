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

let customModelObjectUrl: string | null = null
let sourceVideoObjectUrl: string | null = null

const inputMode = ref<InputMode>("webcam")
const evaluationMode = ref<EvaluationMode>("none")
const selectedNoteId = ref<string | null>(null)
const noteRanges = ref<SessionNoteRange[]>([])
const customModelName = ref<string | null>(null)
const sourceVideoName = ref<string | null>(null)

export const useTrackerSession = () => {
	const { selectedCharacter, setCharacter, clearCharacter } = useSelectedCharacter()

	const activeModelPath = computed(() => customModelObjectUrl ?? selectedCharacter.value?.model ?? null)
	const activeModelLabel = computed(() => customModelName.value ?? selectedCharacter.value?.name ?? null)
	const activeSourceVideoUrl = computed(() => sourceVideoObjectUrl)
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
		if (customModelObjectUrl) {
			URL.revokeObjectURL(customModelObjectUrl)
			customModelObjectUrl = null
		}
		customModelName.value = null
		setCharacter(character)
	}

	const setCustomModel = (file: File | null) => {
		if (customModelObjectUrl) {
			URL.revokeObjectURL(customModelObjectUrl)
			customModelObjectUrl = null
		}

		if (!file) {
			customModelName.value = null
			clearCharacter()
			return
		}

		customModelObjectUrl = URL.createObjectURL(file)
		customModelName.value = file.name
		clearCharacter()
	}

	const setSourceVideo = (file: File | null) => {
		if (sourceVideoObjectUrl) {
			URL.revokeObjectURL(sourceVideoObjectUrl)
			sourceVideoObjectUrl = null
		}

		if (!file) {
			sourceVideoName.value = null
			return
		}

		sourceVideoObjectUrl = URL.createObjectURL(file)
		sourceVideoName.value = file.name
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