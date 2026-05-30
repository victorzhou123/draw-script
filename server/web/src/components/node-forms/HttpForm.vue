<template>
  <div>
    <a-form-item label="请求方法">
      <a-select v-model:value="d.params.method" @change="update()">
        <a-select-option value="GET">GET</a-select-option>
        <a-select-option value="POST">POST</a-select-option>
        <a-select-option value="PUT">PUT</a-select-option>
        <a-select-option value="DELETE">DELETE</a-select-option>
      </a-select>
    </a-form-item>
    <a-form-item label="URL">
      <a-input v-model:value="d.params.url" placeholder="https://api.example.com/..." @change="update()" />
      <div class="tpl-hint">
        使用 <code v-pre>{{变量名}}</code> 引用 context 字段
        <span v-if="ctx.contextFields.value.length" class="tpl-vars">
          —
          <span v-for="f in ctx.contextFields.value" :key="f.name" class="tpl-var-chip" @click="insertVar('url', f.name)">{{ f.name }}</span>
        </span>
      </div>
    </a-form-item>
    <a-form-item label="请求头">
      <div v-for="(h, idx) in httpHeaders" :key="idx" class="field-row">
        <a-input v-model:value="h.key" placeholder="Header名" class="field-name" @change="syncHeaders()" />
        <a-input v-model:value="h.value" placeholder="值" style="flex:2" @change="syncHeaders()" />
        <a-button type="text" size="small" danger @click="removeHeader(idx)">✕</a-button>
      </div>
      <a-button size="small" class="add-field-btn" @click="addHeader">+ 添加请求头</a-button>
    </a-form-item>
    <a-form-item label="请求体 (JSON)">
      <a-textarea v-model:value="d.params.bodyText" :rows="5" placeholder='{"key": "value"}' @change="update()" />
      <div class="tpl-hint">
        使用 <code v-pre>{{变量名}}</code> 引用 context 字段
        <span v-if="ctx.contextFields.value.length" class="tpl-vars">
          —
          <span v-for="f in ctx.contextFields.value" :key="f.name" class="tpl-var-chip" @click="insertVar('bodyText', f.name)">{{ f.name }}</span>
        </span>
      </div>
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const httpHeaders = ref<{ key: string; value: string }[]>([])

watch(d, (data) => {
  if (!data || data.type !== 'http') return
  const h = data.params?.headers ?? {}
  httpHeaders.value = Object.entries(h).map(([key, value]) => ({ key, value: String(value) }))
}, { immediate: true })

function update() { ctx.emitUpdate() }

function addHeader() { httpHeaders.value.push({ key: '', value: '' }); syncHeaders() }
function removeHeader(idx: number) { httpHeaders.value.splice(idx, 1); syncHeaders() }
function syncHeaders() {
  const h: Record<string, string> = {}
  for (const { key, value } of httpHeaders.value) { if (key.trim()) h[key.trim()] = value }
  d.value.params.headers = h
  update()
}

function insertVar(field: 'url' | 'bodyText', varName: string) {
  const current: string = d.value.params[field] ?? ''
  d.value.params[field] = current + `{{${varName}}}`
  update()
}
</script>

<style scoped>
.tpl-hint { font-size: 11px; color: #444; margin-top: 4px; line-height: 1.6; }
.tpl-hint code { background: #1e1e1e; padding: 1px 4px; border-radius: 3px; color: #7ec8e3; font-size: 11px; }
.tpl-vars { color: #444; }
.tpl-var-chip { display: inline-block; background: #111d2c; color: #4096ff; border: 1px solid #1d3c6b; border-radius: 3px; font-size: 10px; padding: 0 5px; margin: 0 2px; cursor: pointer; font-family: 'Consolas', monospace; transition: background 0.15s; }
.tpl-var-chip:hover { background: #1d3c6b; }
.field-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.field-name { flex: 2; min-width: 0; }
.add-field-btn { width: 100%; margin-top: 4px; color: #555 !important; border-color: #303030 !important; background: transparent !important; font-size: 11px !important; }
.add-field-btn:hover { color: #888 !important; border-color: #555 !important; }
</style>
