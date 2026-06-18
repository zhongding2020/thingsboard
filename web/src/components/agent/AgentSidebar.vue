<template>
  <Teleport to="body">
    <Transition name="agent-backdrop">
      <div v-if="visible" class="agent-backdrop" @click="$emit('close')" />
    </Transition>
    <Transition name="agent-sidebar">
      <div v-if="visible" class="agent-sidebar" :class="{ maximized }">
        <slot />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{ visible: boolean; maximized: boolean }>()
defineEmits<{ close: [] }>()
</script>

<style scoped>
.agent-backdrop { position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.3); }
.agent-backdrop-enter-active, .agent-backdrop-leave-active { transition: opacity 0.25s ease; }
.agent-backdrop-enter-from, .agent-backdrop-leave-to { opacity: 0; }
.agent-sidebar { position: fixed; top: 0; right: 0; z-index: 10001; width: 40vw; max-width: 600px; min-width: 380px; height: 100vh; background: var(--el-bg-color); border-left: 1px solid var(--el-border-color-light); box-shadow: -4px 0 32px rgba(0,0,0,0.15); display: flex; flex-direction: column; transition: width 0.3s ease, max-width 0.3s ease; }
.agent-sidebar.maximized { width: 90vw; max-width: 90vw; }
.agent-sidebar-enter-active, .agent-sidebar-leave-active { transition: transform 0.25s ease; }
.agent-sidebar-enter-from, .agent-sidebar-leave-to { transform: translateX(100%); }
</style>
