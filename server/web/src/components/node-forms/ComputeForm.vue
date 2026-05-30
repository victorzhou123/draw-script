<template>
  <div>
    <div class="section-title">Python 代码</div>
    <div class="hint-text">通过 <code>context</code> 字典读写 context 变量。</div>
    <a-form-item :style="{ marginBottom: syntaxError ? '4px' : undefined }">
      <a-textarea
        v-model:value="d.code"
        :rows="10"
        :style="{ fontFamily: 'Consolas, Monaco, monospace', fontSize: '12px', borderColor: syntaxError ? '#ff4d4f' : undefined }"
        placeholder="# 例如：&#10;result = context['x'] * 2&#10;context['result'] = result"
        @change="onCodeChange"
      />
    </a-form-item>
    <div v-if="syntaxError" class="syntax-error-bar">
      <span class="syntax-error-icon">✕</span>
      第 {{ syntaxError.line }} 行<span v-if="syntaxError.col">，第 {{ syntaxError.col }} 列</span>：{{ syntaxError.msg }}
    </div>
    <div class="section-title">
      输出字段
      <a-button size="small" type="link" class="auto-detect-btn" @click="autoDetect">自动检测</a-button>
    </div>
    <div class="hint-text">标注此节点会写入 context 的字段名。</div>
    <div v-for="(f, idx) in d.output_fields" :key="idx" class="return-field-row">
      <a-input v-model:value="d.output_fields[idx]" placeholder="字段名" @change="update()" />
      <a-button type="text" size="small" danger @click="removeOutputField(idx)">✕</a-button>
    </div>
    <a-button size="small" class="add-field-btn" @click="addOutputField">+ 添加字段</a-button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'
import { FORM_CTX } from './useFormContext'
import { api } from '@/services/api'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

interface SyntaxErr { line: number; col: number | null; msg: string }
const syntaxError = ref<SyntaxErr | null>(null)
let _syntaxTimer: ReturnType<typeof setTimeout> | null = null

watch(d, (data) => {
  if (!data || data.type !== 'compute') return
  syntaxError.value = null
  if (_syntaxTimer) { clearTimeout(_syntaxTimer); _syntaxTimer = null }
}, { immediate: true })

function update() { ctx.emitUpdate() }

function onCodeChange() {
  const code: string = d.value.code || ''
  const matches = [...code.matchAll(/context\s*\[\s*['"](\w+)['"]\s*\]\s*=/g)]
  const detected = [...new Set(matches.map(m => m[1]))]
  const existing: string[] = d.value.output_fields ?? []
  const toAdd = detected.filter(f => !existing.includes(f))
  if (toAdd.length > 0) d.value.output_fields = [...existing, ...toAdd]
  scheduleSyntaxCheck(code)
  update()
}

function scheduleSyntaxCheck(code: string) {
  if (_syntaxTimer) clearTimeout(_syntaxTimer)
  if (!code.trim()) { syntaxError.value = null; return }
  _syntaxTimer = setTimeout(async () => {
    try {
      const result = await api.syntaxCheck(code)
      syntaxError.value = result.ok ? null : { line: result.line!, col: result.col ?? null, msg: result.msg! }
    } catch { syntaxError.value = null }
  }, 600)
}

function autoDetect() {
  const code: string = d.value.code || ''
  const matches = [...code.matchAll(/context\s*\[\s*['"](\w+)['"]\s*\]\s*=/g)]
  d.value.output_fields = [...new Set(matches.map(m => m[1]))]
  update()
}

function addOutputField() { d.value.output_fields.push(''); update() }
function removeOutputField(idx: number) { d.value.output_fields.splice(idx, 1); update() }
</script>

<style scoped>
.section-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.8px; margin: 14px 0 6px; display: flex; align-items: center; gap: 6px; }
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.hint-text code { background: #1e1e1e; padding: 1px 4px; border-radius: 3px; color: #7ec8e3; }
.return-field-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.add-field-btn { width: 100%; margin-top: 4px; color: #555 !important; border-color: #303030 !important; background: transparent !important; font-size: 11px !important; }
.add-field-btn:hover { color: #888 !important; border-color: #555 !important; }
.auto-detect-btn { font-size: 11px !important; padding: 0 4px !important; height: auto !important; }
.syntax-error-bar { font-size: 11px; color: #ff4d4f; background: #2a1215; border: 1px solid #58181c; border-radius: 4px; padding: 4px 8px; margin-bottom: 8px; display: flex; align-items: center; gap: 5px; font-family: Consolas, Monaco, monospace; line-height: 1.4; }
.syntax-error-icon { font-size: 10px; flex-shrink: 0; }
</style>
