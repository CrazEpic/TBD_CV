type Vec3Tuple = [number, number, number]

export type ViolinDebugPoint = {
	name: string
	position: Vec3Tuple
	group: "pnp" | "string" | "outline" | "fingering"
}

const RATIO_PER_HALF_STEP = 0.943874312682
const DEFAULT_FINGERING_LOCATIONS_PER_STRING = 7
const DEFAULT_FIXED_STRING_LENGTH_METERS = 0.328

const subtractVec3 = (a: Vec3Tuple, b: Vec3Tuple): Vec3Tuple => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const addScaledVec3 = (a: Vec3Tuple, direction: Vec3Tuple, scalar: number): Vec3Tuple => [a[0] + direction[0] * scalar, a[1] + direction[1] * scalar, a[2] + direction[2] * scalar]

const normalizeVec3 = (vector: Vec3Tuple): Vec3Tuple => {
	const length = Math.hypot(vector[0], vector[1], vector[2])
	if (length <= 1e-8) return [0, 0, 0]
	return [vector[0] / length, vector[1] / length, vector[2] / length]
}

const distanceFromFingerboardEnd = (halfStep: number, stringLength: number) => {
	return stringLength - stringLength * Math.pow(RATIO_PER_HALF_STEP, halfStep)
}

export const useViolinKeypoints = () => {
	const violinKeypoints = {
		unity: {
			pnp_keypoints: {
				chin_anchor: [-0.0427, 0, 0.01908] as Vec3Tuple,
				neck_end: [0, 0.00855, 0.48236] as Vec3Tuple,
			},
			geometry: {
				strings: {
					G: [
						[-0.01682, 0.06121, 0.1583] as Vec3Tuple,
						[-0.00734, 0.00855, 0.48236] as Vec3Tuple,
					],
					D: [
						[-0.00656, 0.06419, 0.1583] as Vec3Tuple,
						[-0.00259, 0.00855, 0.48236] as Vec3Tuple,
					],
					A: [
						[0.00656, 0.06419, 0.1583] as Vec3Tuple,
						[0.00259, 0.00855, 0.48236] as Vec3Tuple,
					],
					E: [
						[0.01682, 0.06121, 0.1583] as Vec3Tuple,
						[0.00734, 0.00855, 0.48236] as Vec3Tuple,
					],
				},
				body_outline: [
					[0, 0, 0] as Vec3Tuple,
					[0.085399, 0, 0.03816] as Vec3Tuple,
					[0.0656, 0, 0.3273] as Vec3Tuple,
					[0, 0, 0.3529] as Vec3Tuple,
					[-0.0656, 0, 0.3273] as Vec3Tuple,
					[-0.085399, 0, 0.03816] as Vec3Tuple,
				],
				bow_contact: null,
			},
		},
	}

	const getDebugPoints = (): ViolinDebugPoint[] => {
		const pnpPoints = Object.entries(violinKeypoints.unity.pnp_keypoints).map(([name, position]) => ({
			name,
			position,
			group: "pnp" as const,
		}))

		const stringPoints = Object.entries(violinKeypoints.unity.geometry.strings).flatMap(([stringName, points]) =>
			points.map((position, index) => ({
				name: `string_${stringName}_${index}`,
				position,
				group: "string" as const,
			})),
		)

		const outlinePoints = violinKeypoints.unity.geometry.body_outline.map((position, index) => ({
			name: `outline_${index}`,
			position,
			group: "outline" as const,
		}))

		return [...pnpPoints, ...stringPoints, ...outlinePoints]
	}

	const getFingeringPoints = (locationsPerString = DEFAULT_FINGERING_LOCATIONS_PER_STRING, fixedStringLengthMeters = DEFAULT_FIXED_STRING_LENGTH_METERS): ViolinDebugPoint[] => {
		if (locationsPerString <= 0) return []

		return Object.entries(violinKeypoints.unity.geometry.strings).flatMap(([stringName, segment]) => {
			const bridgeSide = segment[0]
			const fingerboardEnd = segment[1]
			const measuredDirection = subtractVec3(bridgeSide, fingerboardEnd)
			const measuredLength = Math.hypot(measuredDirection[0], measuredDirection[1], measuredDirection[2])
			if (measuredLength <= 1e-8) return []

			const direction = normalizeVec3(measuredDirection)
			const targetLength = fixedStringLengthMeters > 0 ? fixedStringLengthMeters : measuredLength

			return Array.from({ length: locationsPerString }, (_, halfStep) => {
				const distance = distanceFromFingerboardEnd(halfStep, targetLength)
				const position = addScaledVec3(fingerboardEnd, direction, distance)
				// flip X because unity model is left-handed but three.js is right-handed
				const flippedPosition: Vec3Tuple = [-position[0], position[1], position[2]]
				return {
					name: `fingering_${stringName}_${halfStep}`,
					position: flippedPosition,
					group: "fingering" as const,
				}
			})
		})
	}

	return {
		violinKeypoints,
		getDebugPoints,
		getFingeringPoints,
	}
}
