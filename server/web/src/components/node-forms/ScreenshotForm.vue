<template>
  <div>
    <a-form-item label="截图区域">
      <a-select v-model:value="d.range_marker" :style="{ width: '100%' }" placeholder="选择方框标记作为截图区域" allow-clear @change="update()">
        <a-select-option v-for="m in ctx.availableMarkers.value" :key="m.name" :value="m.name">
          <span class="marker-menu-type" :class="`type-${m.type}`">{{ m.type === 'point' ? '点' : '方框' }}</span>
          {{ m.name }}
        </a-select-option>
      </a-select>
      <div class="hint-text" style="margin-top:4px">留空则截取全屏</div>
      <div v-if="!ctx.availableMarkers.value.length" class="hint-text" style="margin-top:2px">
        当前项目暂无标记，请先在项目中添加方框类型标记
      </div>
    </a-form-item>

    <a-form-item label="存入 Context">
      <a-auto-complete
        v-model:value="d.result_var"
        :options="ctx.contextFields.value.map((f: any) => ({ value: f.name }))"
        placeholder="context 字段名（必填）"
        allow-clear
        @change="update()"
      />
      <div class="hint-text" style="margin-top:4px">截图以 base64 格式存入指定字段</div>
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

function update() { ctx.emitUpdate() }
</script>

<style scoped>
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.marker-menu-type { display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-right: 6px; font-weight: 600; }
.type-point { background: #111d2c; color: #1890ff; }
.type-box { background: #2b2111; color: #faad14; }
</style>
