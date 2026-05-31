<template>
  <div>
    <div class="section-title">Context 字段定义</div>
    <div class="hint-text">API 调用时同名参数自动注入；否则使用默认值。</div>
    <div v-for="(field, idx) in d.fields" :key="idx" class="field-row">
      <a-input v-model:value="field.name" placeholder="字段名" class="field-name" @change="update()" />
      <a-select v-model:value="field.type" class="field-type" @change="update()">
        <a-select-option value="any">any</a-select-option>
        <a-select-option value="str">str</a-select-option>
        <a-select-option value="int">int</a-select-option>
        <a-select-option value="float">float</a-select-option>
        <a-select-option value="bool">bool</a-select-option>
        <a-select-option value="list">list</a-select-option>
        <a-select-option value="dict">dict</a-select-option>
      </a-select>
      <a-input v-model:value="field.default" placeholder="默认值" class="field-default" @change="update()" />
      <a-button type="text" size="small" danger @click="removeField(idx)">✕</a-button>
    </div>
    <a-button size="small" class="add-field-btn" @click="addField">+ 添加字段</a-button>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
function update() { ctx.emitUpdate() }
function addField() { d.value.fields.push({ name: '', type: 'any', default: '' }); update() }
function removeField(idx: number) { d.value.fields.splice(idx, 1); update() }
</script>

<style scoped>
.section-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.8px; margin: 14px 0 6px; }
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.field-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.field-name { flex: 2; min-width: 0; }
.field-type { flex: 1.2; min-width: 0; }
.field-default { flex: 1.5; min-width: 0; }
.add-field-btn { width: 100%; margin-top: 4px; color: #555 !important; border-color: #303030 !important; background: transparent !important; font-size: 11px !important; }
.add-field-btn:hover { color: #888 !important; border-color: #555 !important; }
</style>
