<template>
  <div class="draw-node" :class="[`node-type-${nodeType}`, { 'node-active': isActive }]">
    <div class="node-inner">
      <component :is="iconComp" class="node-icon" />
      <div class="node-label">{{ displayLabel }}</div>
    </div>
    <div v-if="statusBadge === 'done'" class="status-badge status-done">
      <CheckOutlined />
    </div>
    <a-tooltip
      v-else-if="statusBadge === 'error'"
      placement="topRight"
      :title="nodeErrorText"
      :overlay-inner-style="{ fontSize: '12px', maxWidth: '320px', whiteSpace: 'pre-line', wordBreak: 'break-word' }"
    >
      <div class="status-badge status-error">
        <CloseOutlined />
      </div>
    </a-tooltip>
    <a-tooltip
      v-else-if="statusBadge === 'warning'"
      placement="topRight"
      :title="nodeWarningText"
      :overlay-inner-style="{ fontSize: '12px', maxWidth: '320px', whiteSpace: 'pre-line', wordBreak: 'break-word' }"
    >
      <div class="status-badge status-warning">
        <WarningOutlined />
      </div>
    </a-tooltip>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onMounted, onBeforeUnmount } from 'vue'
import { CheckOutlined, CloseOutlined, WarningOutlined } from '@ant-design/icons-vue'
import { useExecutionStore } from '@/stores/executionStore'
import { useScriptStore } from '@/stores/scriptStore'
import { ICON_MAP } from './index'

const props = defineProps<{
  icon: string
  label: string
  nodeType: string
}>()

const getNode = inject<() => any>('getNode')
const executionStore = useExecutionStore()
const scriptStore = useScriptStore()

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
  return node && executionStore.activeNodeIds.has(node.id)
})

const statusBadge = computed(() => {
  const node = getNode?.()
  if (!node) return null
  const execStatus = executionStore.nodeStatus[node.id]
  if (execStatus) return execStatus
  const check = scriptStore.nodeCheckResults[node.id]
  return check?.status ?? null
})

const nodeErrorText = computed(() => {
  const node = getNode?.()
  if (!node) return ''
  const logs = executionStore.nodeLogsFor(node.id)
  if (logs.length > 0) return logs.map(l => l.replace(/^\s*ERROR:\s*/, '')).join('\n')
  const check = scriptStore.nodeCheckResults[node.id]
  return check?.message || '执行错误'
})

const nodeWarningText = computed(() => {
  const node = getNode?.()
  if (!node) return ''
  return scriptStore.nodeCheckResults[node.id]?.message || ''
})
</script>

<style scoped>
.draw-node {
  position: relative;
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
.status-badge {
  position: absolute;
  right: -6px;
  bottom: -6px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #fff;
  border: 1.5px solid #141414;
  z-index: 2;
}
.status-badge.status-done    { background: #52c41a; }
.status-badge.status-error   { background: #ff4d4f; }
.status-badge.status-warning { background: #faad14; }
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

.node-type-context-edit { border-color: #eb2f96; background: #1a0a14; }
.node-type-context-edit .node-icon, .node-type-context-edit .node-label { color: #eb2f96; }

.node-type-crawl { border-color: #389e0d; background: #0d1a0a; }
.node-type-crawl .node-icon, .node-type-crawl .node-label { color: #52c41a; }

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 14px rgba(82,196,26,0.55); }
  50%       { box-shadow: 0 0 28px rgba(82,196,26,0.9); }
}
</style>
