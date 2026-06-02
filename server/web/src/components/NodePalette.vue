<template>
  <div class="node-palette">
    <div class="palette-section-title">节点类型</div>
    <div
      v-for="def in NODE_DEFS"
      :key="def.shape"
      class="palette-item"
      :class="`palette-${def.shape.replace('node-', '')}`"
      draggable="false"
      @mousedown="onDragStart(def, $event)"
    >
      <component :is="ICON_MAP[def.icon]" class="palette-icon" />
      <span class="palette-label">{{ def.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NODE_DEFS, ICON_MAP } from './nodes/index'

const emit = defineEmits<{
  (e: 'dragStart', shape: string, defaultData: object, event: MouseEvent): void
}>()

function onDragStart(def: typeof NODE_DEFS[0], event: MouseEvent) {
  emit('dragStart', def.shape, {}, event)
}
</script>

<style scoped>
.node-palette {
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow-y: auto;
  height: 100%;
}
.palette-section-title {
  font-size: 10px;
  color: #444;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  margin-bottom: 8px;
  padding: 0 6px;
}
.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  border: 1px solid transparent;
  background: transparent;
  cursor: grab;
  transition: all 0.15s;
  user-select: none;
}
.palette-item:hover {
  background: #1f1f1f;
  border-color: #303030;
}
.palette-item:active { cursor: grabbing; }
.palette-icon {
  font-size: 14px;
  width: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.palette-label { font-size: 12px; color: #999; font-weight: 500; }

/* Per-type accent colors */
.palette-start    .palette-icon { color: #52c41a; }
.palette-end      .palette-icon { color: #ff4d4f; }
.palette-action   .palette-icon { color: #1890ff; }
.palette-screenshot .palette-icon { color: #a0d911; }
.palette-vision   .palette-icon { color: #9254de; }
.palette-condition .palette-icon { color: #faad14; }
.palette-delay    .palette-icon { color: #fa8c16; }
.palette-loop     .palette-icon { color: #597ef7; }
.palette-wait     .palette-icon { color: #2db7f5; }
.palette-http     .palette-icon { color: #13c2c2; }
.palette-compute  .palette-icon { color: #36cfc9; }
.palette-script   .palette-icon { color: #b37feb; }
.palette-watch    .palette-icon { color: #ff7a45; }

.palette-start:hover    .palette-label { color: #52c41a; }
.palette-end:hover      .palette-label { color: #ff4d4f; }
.palette-action:hover   .palette-label { color: #1890ff; }
.palette-screenshot:hover .palette-label { color: #a0d911; }
.palette-vision:hover   .palette-label { color: #9254de; }
.palette-condition:hover .palette-label { color: #faad14; }
.palette-delay:hover    .palette-label { color: #fa8c16; }
.palette-loop:hover     .palette-label { color: #597ef7; }
.palette-wait:hover     .palette-label { color: #2db7f5; }
.palette-http:hover     .palette-label { color: #13c2c2; }
.palette-compute:hover  .palette-label { color: #36cfc9; }
.palette-script:hover   .palette-label { color: #b37feb; }
.palette-watch:hover    .palette-label { color: #ff7a45; }
</style>
