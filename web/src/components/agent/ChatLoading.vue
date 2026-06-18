<template>
  <div class="loading-indicator">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
  </div>
</template>

<style scoped>
.loading-indicator { display: flex; align-items: center; gap: 6px; padding: 10px 14px; align-self: flex-start; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--el-color-primary); opacity: 0.35; animation: dot-bounce 1.4s ease-in-out infinite both; }
.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes dot-bounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.35; } 40% { transform: translateY(-6px); opacity: 1; } }
</style>
