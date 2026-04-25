<template>
	<div class="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
		<div class="flex items-center justify-between gap-3">
			<div>
				<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Note target</p>
				<h2 class="text-lg font-medium text-white">Violin positions</h2>
			</div>
			<span class="text-xs text-slate-400">32 options</span>
		</div>

		<div class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
			<UButton
				v-for="note in noteOptions"
				:key="note.id"
				:size="selectedNoteId === note.id ? 'md' : 'sm'"
				:color="selectedNoteId === note.id ? 'primary' : 'neutral'"
				:variant="selectedNoteId === note.id ? 'solid' : 'outline'"
				@click="session.setSelectedNoteId(note.id)"
			>
				{{ note.label }}
			</UButton>
		</div>

		<div v-if="context === 'labeling'" class="mt-4 space-y-4">
			<div class="grid gap-3 rounded-xl border border-white/10 bg-black/30 p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<p class="text-sm font-medium text-white">Labeling timeline</p>
						<p class="text-xs text-slate-400">Assign the correct note to each time segment.</p>
					</div>
					<div class="flex gap-2">
						<UButton size="xs" variant="outline" @click="addRange">Add segment</UButton>
						<UButton size="xs" variant="outline" @click="exportLabeling">Export</UButton>
						<UButton size="xs" variant="outline" @click="importLabeling">Import</UButton>
					</div>
				</div>

				<div class="grid gap-3 md:grid-cols-[1fr_auto]">
					<UTextarea v-model="labelingJson" :rows="8" placeholder="Paste labeling JSON here to import or export it." />
					<div class="rounded-xl border border-white/10 bg-slate-950/50 p-3 text-xs text-slate-300 md:w-56">
						<p class="font-medium text-white">Format</p>
						<p class="mt-2">`selectedNoteId` + `noteRanges[]`</p>
						<p class="mt-1">Each segment stores a note and start/end timestamps.</p>
					</div>
				</div>

				<div v-if="session.noteRanges.length" class="space-y-3">
					<div v-for="range in session.noteRanges" :key="range.id" class="rounded-xl border border-white/10 bg-slate-950/50 p-3">
						<div class="mb-3 flex items-center justify-between gap-2">
							<p class="text-sm font-medium text-white">Segment</p>
							<UButton size="xs" color="error" variant="outline" @click="session.deleteNoteRange(range.id)">Delete</UButton>
						</div>

						<div class="grid gap-3 md:grid-cols-[1fr_repeat(2,minmax(0,8rem))]">
							<USelectMenu
								:items="noteOptions"
								:model-value="getRangeNoteOption(range)"
								:searchable="true"
								placeholder="Choose note"
								class="w-full"
								@update:model-value="(value) => setRangeNoteValue(range.id, value)"
							/>

							<UInput v-model="range.startMs" type="number" min="0" step="10" placeholder="Start ms" />
							<UInput v-model="range.endMs" type="number" min="0" step="10" placeholder="End ms" />
						</div>
					</div>
				</div>
			</div>
		</div>

		<div v-else class="mt-4 rounded-xl border border-white/10 bg-black/30 p-3 text-sm text-slate-300">
			<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Current note</p>
			<p class="mt-1">{{ session.selectedNote?.label || 'No note selected' }}</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { VIOLIN_NOTE_OPTIONS, type ViolinNoteOption } from "@/utils/violinNotes"
import { useTrackerSession, type SessionNoteRange } from "@/composables/useTrackerSession"

const props = defineProps<{
	context: "live" | "labeling"
}>()

const session = useTrackerSession()
const noteOptions = VIOLIN_NOTE_OPTIONS
const labelingJson = ref("")

const addRange = () => {
	session.addNoteRange({
		id: crypto.randomUUID(),
		noteId: session.selectedNoteId.value ?? noteOptions[0].id,
		startMs: 0,
		endMs: null,
	})
}

const exportLabeling = () => {
	labelingJson.value = session.exportLabeling()
}

const importLabeling = () => {
	if (!labelingJson.value.trim()) return
	session.importLabeling(labelingJson.value)
}

const getRangeNoteOption = (range: SessionNoteRange) => {
	return noteOptions.find((option) => option.id === range.noteId) ?? noteOptions[0]
}

const setRangeNoteValue = (rangeId: string, value: string | ViolinNoteOption | null) => {
	const noteId = typeof value === "string" ? value : value?.id ?? noteOptions[0].id
	session.updateNoteRange(rangeId, { noteId })
}
</script>