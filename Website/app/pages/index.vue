<template>
	<div class="min-h-screen bg-[linear-gradient(180deg,#050816_0%,#08101d_48%,#05070d_100%)]">
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
