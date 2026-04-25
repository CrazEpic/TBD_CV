export type ViolinStringName = "G" | "D" | "A" | "E"

export type ViolinNoteOption = {
	id: string
	stringName: ViolinStringName
	semitoneOffset: number
	label: string
}

const VIOLIN_STRINGS: ViolinStringName[] = ["G", "D", "A", "E"]

export const createViolinNoteOptions = (): ViolinNoteOption[] => {
	return VIOLIN_STRINGS.flatMap((stringName) => {
		return Array.from({ length: 8 }, (_, semitoneOffset) => {
			const label = semitoneOffset === 0 ? `${stringName} open` : `${stringName} +${semitoneOffset}`
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