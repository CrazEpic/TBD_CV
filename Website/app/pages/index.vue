<template>
	<div class="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(251,191,36,0.14),_transparent_32%),linear-gradient(180deg,#050816_0%,#08101d_48%,#05070d_100%)]">
		<TrackerSetupPanel @start="startSession" />
	</div>
</template>

<script setup lang="ts">
definePageMeta({
	layout: false,
})

const router = useRouter()

const startSession = () => {
	router.push("/tracker")
}
</script>
