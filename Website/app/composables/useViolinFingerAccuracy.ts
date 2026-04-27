import { ref } from "vue"
import type * as THREE from "three"
import type { ViolinNoteOption, ViolinStringName } from "@/utils/violinNotes"
import type { LeftHandFinger } from "@/composables/useVRMRig"

export type FingerAccuracyStatus = "tracked" | "missing-target" | "missing-finger" | "open-string-pending"

export type FingerAccuracyReading = {
	noteId: string
	stringName: ViolinStringName
	positionOnString: number
	finger: LeftHandFinger | null
	status: FingerAccuracyStatus
	distanceMeters: number | null
	timestamp: number
	targetWorld: { x: number; y: number; z: number } | null
	fingerWorld: { x: number; y: number; z: number } | null
}

type AccuracyDependencies = {
	getTargetWorldPoint: (stringName: ViolinStringName, positionOnString: number) => THREE.Vector3 | null
	getLeftDistalFingerWorldPoint: (finger: LeftHandFinger) => THREE.Vector3 | null
}

export const selectLeftFingerForFirstPosition = (positionOnString: number): LeftHandFinger => {
	const index = Math.max(0, Math.floor(positionOnString))
	if (index <= 1) return "index"
	if (index <= 3) return "middle"
	if (index <= 5) return "ring"
	return "pinky"
}

const getFirstPositionSemitoneIndex = (note: ViolinNoteOption): number | null => {
	const semitoneOffset = Math.floor(note.semitoneOffset)
	if (semitoneOffset <= 0) return null
	return semitoneOffset - 1
}

export const isOpenStringNote = (note: ViolinNoteOption) => {
	// Stub for future open-string metric pipeline.
	return getFirstPositionSemitoneIndex(note) === null
}

export const computeOpenStringDistance = (_note: ViolinNoteOption) => {
	// Stub for future open-string metric pipeline.
	return null
}

const asPoint = (value: THREE.Vector3 | null) => {
	if (!value) return null
	return { x: value.x, y: value.y, z: value.z }
}

export const useViolinFingerAccuracy = () => {
	const latestReading = ref<FingerAccuracyReading | null>(null)

	const updateForSelectedNote = (
		selectedNote: ViolinNoteOption | null,
		dependencies: AccuracyDependencies,
		timestamp = performance.now(),
	): FingerAccuracyReading | null => {
		if (!selectedNote) {
			latestReading.value = null
			return null
		}

		const positionOnString = getFirstPositionSemitoneIndex(selectedNote)

		if (isOpenStringNote(selectedNote)) {
			latestReading.value = {
				noteId: selectedNote.id,
				stringName: selectedNote.stringName,
				positionOnString: -1,
				finger: null,
				status: "open-string-pending",
				distanceMeters: computeOpenStringDistance(selectedNote),
				timestamp,
				targetWorld: null,
				fingerWorld: null,
			}
			return latestReading.value
		}

		if (positionOnString == null) {
			latestReading.value = null
			return null
		}

		const finger = selectLeftFingerForFirstPosition(positionOnString)
		const targetWorld = dependencies.getTargetWorldPoint(selectedNote.stringName, positionOnString)
		if (!targetWorld) {
			latestReading.value = {
				noteId: selectedNote.id,
				stringName: selectedNote.stringName,
				positionOnString,
				finger,
				status: "missing-target",
				distanceMeters: null,
				timestamp,
				targetWorld: null,
				fingerWorld: null,
			}
			return latestReading.value
		}

		const fingerWorld = dependencies.getLeftDistalFingerWorldPoint(finger)
		if (!fingerWorld) {
			latestReading.value = {
				noteId: selectedNote.id,
				stringName: selectedNote.stringName,
				positionOnString,
				finger,
				status: "missing-finger",
				distanceMeters: null,
				timestamp,
				targetWorld: asPoint(targetWorld),
				fingerWorld: null,
			}
			return latestReading.value
		}

		latestReading.value = {
			noteId: selectedNote.id,
			stringName: selectedNote.stringName,
			positionOnString,
			finger,
			status: "tracked",
			distanceMeters: targetWorld.distanceTo(fingerWorld),
			timestamp,
			targetWorld: asPoint(targetWorld),
			fingerWorld: asPoint(fingerWorld),
		}
		return latestReading.value
	}

	const reset = () => {
		latestReading.value = null
	}

	return {
		latestReading,
		updateForSelectedNote,
		reset,
	}
}
