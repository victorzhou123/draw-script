<template>
  <div>
    <a-form-item label="引用脚本">
      <a-select v-model:value="d.script_id" :style="{ width: '100%' }" placeholder="选择要调用的脚本"
        allow-clear show-search option-filter-prop="label" @change="update()">
        <a-select-option v-for="s in ctx.otherScripts.value" :key="s.id" :value="s.id" :label="s.name">
          {{ s.name }}
        </a-select-option>
      </a-select>
    </a-form-item>
    <div class="hint-text">父脚本的 context 变量传入子脚本；子脚本 End 节点返回的字段合并回父脚本。</div>
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
.hint-text { font-size: 11px; color: #444; line-height: 1.5; }
</style>
