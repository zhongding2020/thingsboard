<template>
  <div class="field-grid">
    <div class="field-section">
      <h4 class="section-title">📊 参数字段 (Feature)</h4>
      <div class="card-grid">
        <div
          v-for="f in props.fields.features"
          :key="f.name"
          class="field-card"
          :class="{ selected: selectedFeatures.includes(f.name) }"
          @click="toggleFeature(f.name)"
        >
          <div class="card-checkbox">
            <span v-if="selectedFeatures.includes(f.name)" class="check filled">✓</span>
            <span v-else class="check empty"></span>
          </div>
          <div class="card-body">
            <div class="card-name">{{ f.name }}</div>
            <div class="card-type">{{ f.type }}{{ f.min != null ? ` · ${f.min}–${f.max}` : '' }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="field-section">
      <h4 class="section-title">🎯 结果字段 (Target)</h4>
      <div class="card-grid">
        <div
          v-for="t in props.fields.targets"
          :key="t.name"
          class="field-card target"
          :class="{ selected: selectedTargets.includes(t.name) }"
          @click="toggleTarget(t.name)"
        >
          <div class="card-checkbox">
            <span v-if="selectedTargets.includes(t.name)" class="check filled target">✓</span>
            <span v-else class="check empty"></span>
          </div>
          <div class="card-body">
            <div class="card-name">{{ t.name }}</div>
            <div class="card-type">{{ t.type }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="field-actions">
      <el-button text size="small" @click="selectAllFeatures">全选参数</el-button>
      <el-button text size="small" @click="selectAllTargets">全选结果</el-button>
      <el-button text size="small" @click="clearAll">清空</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { FieldMeta } from '@/api/analysis'

const props = defineProps<{
  fields: { features: FieldMeta[]; targets: FieldMeta[] }
}>()

const emit = defineEmits<{
  'update:selectedFeatures': [names: string[]]
  'update:selectedTargets': [names: string[]]
}>()

const selectedFeatures = ref<string[]>(props.fields.features.map((f) => f.name))
const selectedTargets = ref<string[]>(
  props.fields.targets.filter((f) => f.type === 'numeric').map((f) => f.name)
)

function toggleFeature(name: string) {
  const idx = selectedFeatures.value.indexOf(name)
  if (idx >= 0) {
    selectedFeatures.value.splice(idx, 1)
  } else {
    selectedFeatures.value.push(name)
  }
  emit('update:selectedFeatures', [...selectedFeatures.value])
}

function toggleTarget(name: string) {
  const idx = selectedTargets.value.indexOf(name)
  if (idx >= 0) {
    selectedTargets.value.splice(idx, 1)
  } else {
    selectedTargets.value.push(name)
  }
  emit('update:selectedTargets', [...selectedTargets.value])
}

function selectAllFeatures() {
  selectedFeatures.value = props.fields.features.map((f) => f.name)
  emit('update:selectedFeatures', [...selectedFeatures.value])
}

function selectAllTargets() {
  selectedTargets.value = props.fields.targets.map((t) => t.name)
  emit('update:selectedTargets', [...selectedTargets.value])
}

function clearAll() {
  selectedFeatures.value = []
  selectedTargets.value = []
  emit('update:selectedFeatures', [])
  emit('update:selectedTargets', [])
}
</script>

<style scoped>
.field-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}
.field-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--el-bg-color);
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.field-card.selected {
  border-color: var(--el-color-primary);
  background: rgba(var(--el-color-primary-rgb, 64, 158, 255), 0.06);
}
.field-card.target.selected {
  border-color: #a855f7;
  background: rgba(168, 85, 247, 0.06);
}
.field-card:hover {
  border-color: var(--el-color-primary-light-3);
}
.card-checkbox {
  flex-shrink: 0;
}
.check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  font-size: 11px;
}
.check.empty {
  border: 2px solid var(--el-border-color-darker);
}
.check.filled {
  background: var(--el-color-primary);
  color: #fff;
  border-color: var(--el-color-primary);
}
.check.filled.target {
  background: #a855f7;
  border-color: #a855f7;
}
.card-body {
  min-width: 0;
}
.card-name {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-type {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  margin-top: 2px;
}
.field-actions {
  display: flex;
  gap: 4px;
}
</style>
