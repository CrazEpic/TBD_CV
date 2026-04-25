export type ViolinStringName = "G" | "D" | "A" | "E"

export type ViolinNoteOption = {
	id: string
	stringName: ViolinStringName
	semitoneOffset: number
	label: string
}

const VIOLIN_STRINGS: ViolinStringName[] = ["G", "D", "A", "E"]
const OPEN_STRING_MIDI: Record<ViolinStringName, number> = {
	G: 55, // G3
	D: 62, // D4
	A: 69, // A4
	E: 76, // E5
}

const NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"] as const
const ENHARMONIC_FLATS: Record<string, string> = {
	"C#": "Db",
	"D#": "Eb",
	"F#": "Gb",
	"G#": "Ab",
	"A#": "Bb",
}

const SEMITONES_PER_STRING = 8

const formatPitchLabel = (midiNote: number): string => {
	const octave = Math.floor(midiNote / 12) - 1
	const noteIndex = midiNote % 12
	const sharpName = NOTE_NAMES_SHARP[noteIndex] as string
	const flatName = sharpName in ENHARMONIC_FLATS ? ENHARMONIC_FLATS[sharpName] : null

	if (flatName) {
		return `${sharpName}${octave} / ${flatName}${octave}`
	}

	return `${sharpName}${octave}`
}

export const createViolinNoteOptions = (): ViolinNoteOption[] => {
	return VIOLIN_STRINGS.flatMap((stringName) => {
		return Array.from({ length: SEMITONES_PER_STRING }, (_, semitoneOffset) => {
			const pitchLabel = formatPitchLabel(OPEN_STRING_MIDI[stringName] + semitoneOffset)
			const label = pitchLabel
			return {
				id: `${stringName}-${semitoneOffset}`,
				stringName,
				semitoneOffset,
				label,
			}
		})
	})
}

export const VIOLIN_NOTE_OPTIONS = createViolinNoteOptions()