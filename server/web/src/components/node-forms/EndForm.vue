<template>
  <div>
    <div class="section-title">返回字段</div>
    <div class="hint-text">新增的 context 字段会自动加入，手动删除的不会再自动添加。</div>
    <template v-if="d.return_fields?.length">
      <div v-for="(f, idx) in d.return_fields" :key="idx" class="field-group">
        <div class="return-field-row">
          <span class="ctx-dot certain" />
          <span class="field-name-text">{{ f }}</span>
          <a-button type="text" size="small" danger @click="removeReturnField(idx)">✕</a-button>
        </div>
        <a-input
          :value="descMap[f] ?? ''"
          placeholder="字段说明（可选）"
          class="field-desc"
          @input="(e: any) => onDescChange(f, e.target.value)"
        />
      </div>
    </template>
    <div v-else class="hint-text">上游暂无 context 变量</div>
    <div class="return-field-row" style="margin-top:6px">
      <a-input v-model:value="newReturnField" placeholder="手动输入字段名" size="small" style="flex:1" @pressEnter="addReturnFieldManual" />
      <a-button size="small" @click="addReturnFieldManual">+</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
const newReturnField = ref('')

const descMap = computed<Record<string, string>>(() => d.value?.return_field_descriptions ?? {})

function onDescChange(fieldName: string, value: string) {
  if (!d.value.return_field_descriptions) d.value.return_field_descriptions = {}
  d.value.return_field_descriptions[fieldName] = value
  ctx.emitUpdate()
}

// Auto-add new context fields (only ones not previously seen)
watch(ctx.contextFields, (fields) => {
  if (d.value?.type !== 'end') return
  const known = new Set<string>(d.value.known_fields ?? [])
  const added = fields.map((f: any) => f.name).filter((n: string) => !known.has(n))
  if (added.length === 0) return
  d.value.return_fields = [...(d.value.return_fields ?? []), ...added]
  d.value.known_fields = [...(d.value.known_fields ?? []), ...added]
  ctx.emitUpdate()
})

function update() { ctx.emitUpdate() }

function addReturnFieldManual() {
  const name = newReturnField.value.trim()
  if (!name) return
  if (!d.value.return_fields.includes(name)) d.value.return_fields.push(name)
  if (!d.value.known_fields) d.value.known_fields = []
  if (!d.value.known_fields.includes(name)) d.value.known_fields.push(name)
  newReturnField.value = ''
  update()
}

function removeReturnField(idx: number) {
  const name = d.value.return_fields[idx]
  d.value.return_fields.splice(idx, 1)
  if (d.value.return_field_descriptions) {
    delete d.value.return_field_descriptions[name]
  }
  update()
}
</script>

<style scoped>
.section-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.8px; margin: 14px 0 6px; }
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; }
.field-group { margin-bottom: 8px; }
.return-field-row { display: flex; align-items: center; gap: 4px; margin-bottom: 3px; }
.field-name-text { flex: 1; font-size: 13px; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; flex-shrink: 0; }
.ctx-dot.certain { background: #52c41a; }
.field-desc { width: 100%; font-size: 11px !important; background: transparent !important; border-color: #252525 !important; color: #555 !important; }
.field-desc:focus { border-color: #1890ff !important; color: #888 !important; }
</style>
