<template>
  <div class="draw-node" :class="[`node-type-${nodeType}`, { 'node-active': isActive }]">
    <div class="node-inner">
      <component :is="iconComp" class="node-icon" />
      <div class="node-label">{{ displayLabel }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onMounted, onBeforeUnmount } from 'vue'
import { useExecutionStore } from '@/stores/executionStore'
import { ICON_MAP } from './index'

const props = defineProps<{
  icon: string
  label: string
  nodeType: string
}>()

const getNode = inject<() => any>('getNode')
const executionStore = useExecutionStore()

const iconComp = computed(() => ICON_MAP[props.icon])

const customLabel = ref('')

function syncLabel() {
  customLabel.value = getNode?.()?.getData()?.label?.trim() ?? ''
}

onMounted(() => {
  const node = getNode?.()
  if (!node) return
  syncLabel()
  node.on('change:data', syncLabel)
})

onBeforeUnmount(() => {
  getNode?.()?.off('change:data', syncLabel)
})

const displayLabel = computed(() => customLabel.value || props.label)

const isActive = computed(() => {
  const node = getNode?.()
  return node && executionStore.activeNodeId === node.id
})
</script>

<style scoped>
.draw-node {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #1f1f1f;
  border: 1.5px solid #3a3a3a;
  cursor: pointer;
  transition: all 0.18s;
  user-select: none;
}
.draw-node:not(.node-type-condition):hover { box-shadow: 0 0 0 2px rgba(255,255,255,0.1); }
.draw-node.node-active:not(.node-type-condition) {
  border-color: #52c41a;
  box-shadow: 0 0 14px rgba(82,196,26,0.55);
  animation: pulse 1.2s infinite;
}
.node-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.node-icon {
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.node-label {
  margin-top: 5px;
  font-size: 11px;
  font-weight: 500;
  text-align: center;
  padding: 0 4px;
  word-break: break-word;
  letter-spacing: 0.2px;
}

/* Per-type colors */
.node-type-start  { border-color: #52c41a; background: #162312; }
.node-type-start  .node-icon, .node-type-start  .node-label { color: #52c41a; }
.node-type-start  { border-radius: 50%; }

.node-type-end    { border-color: #ff4d4f; background: #2a1215; }
.node-type-end    .node-icon, .node-type-end    .node-label { color: #ff4d4f; }
.node-type-end    { border-radius: 50%; }

.node-type-action { border-color: #1890ff; background: #111d2c; }
.node-type-action .node-icon, .node-type-action .node-label { color: #1890ff; }

.node-type-screenshot { border-color: #a0d911; background: #1d2c00; }
.node-type-screenshot .node-icon, .node-type-screenshot .node-label { color: #a0d911; }

.node-type-vision { border-color: #722ed1; background: #1a0a2e; }
.node-type-vision .node-icon, .node-type-vision .node-label { color: #9254de; }

.node-type-condition {
  background: transparent;
  border: none;
  position: relative;
}
.node-type-condition::before {
  content: '';
  position: absolute;
  inset: 0;
  background: #2b2111;
  border: 1.5px solid #faad14;
  border-radius: 8px;
  transform: rotate(45deg);
  pointer-events: none;
}
.node-type-condition:hover::before {
  box-shadow: 0 0 0 2px rgba(255,255,255,0.1);
}
.node-type-condition.node-active::before {
  border-color: #52c41a;
  box-shadow: 0 0 14px rgba(82,196,26,0.55);
  animation: pulse 1.2s infinite;
}
.node-type-condition .node-inner { position: relative; z-index: 1; }
.node-type-condition .node-icon,
.node-type-condition .node-label { color: #faad14; }

.node-type-delay { border-color: #fa8c16; background: #2b1d11; }
.node-type-delay .node-icon, .node-type-delay .node-label { color: #fa8c16; }

.node-type-loop  { border-color: #2f54eb; background: #131629; }
.node-type-loop  .node-icon, .node-type-loop  .node-label { color: #597ef7; }

.node-type-wait  { border-color: #2db7f5; background: #0a1e2e; }
.node-type-wait  .node-icon, .node-type-wait  .node-label { color: #2db7f5; }

.node-type-http  { border-color: #13c2c2; background: #112123; }
.node-type-http  .node-icon, .node-type-http  .node-label { color: #13c2c2; }


@keyframes pulse {
  0%, 100% { box-shadow: 0 0 14px rgba(82,196,26,0.55); }
  50%       { box-shadow: 0 0 28px rgba(82,196,26,0.9); }
}
</style>
