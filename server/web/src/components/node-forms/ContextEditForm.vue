<template>
  <div>
    <div v-for="(op, idx) in operations" :key="idx" class="op-block">
      <div class="op-header">
        <a-select v-model:value="op.op" size="small" class="op-type-select" @change="update()">
          <a-select-option value="set">Set</a-select-option>
          <a-select-option value="delete">Delete</a-select-option>
          <a-select-option value="rename">Rename</a-select-option>
        </a-select>
        <a-button type="text" size="small" danger class="op-del" @click="removeOp(idx)">✕</a-button>
      </div>

      <!-- Set: key = value -->
      <template v-if="op.op === 'set'">
        <div class="op-row">
          <a-auto-complete
            v-model:value="op.key"
            :options="contextOptions"
            placeholder="key"
            class="op-key"
            @change="update()"
          />
          <span class="op-sym">=</span>
          <a-select
            v-if="op.value_type === 'bool'"
            v-model:value="op.value"
            class="op-val"
            allow-clear
            @change="update()"
          >
            <a-select-option value="True">True</a-select-option>
            <a-select-option value="False">False</a-select-option>
          </a-select>
          <a-input
            v-else
            v-model:value="op.value"
            placeholder="value 或 {{变量名}}"
            class="op-val"
            @change="update()"
          />
          <a-select v-model:value="op.value_type" size="small" class="op-vtype" @change="update()">
            <a-select-option value="">auto</a-select-option>
            <a-select-option v-for="t in VALUE_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
          </a-select>
        </div>
      </template>

      <!-- Delete: remove key from context -->
      <template v-else-if="op.op === 'delete'">
        <div class="op-row">
          <a-select
            v-model:value="op.key"
            :options="contextOptions"
            placeholder="选择要删除的 key"
            allow-clear
            show-search
            class="op-full"
            @change="update()"
          />
        </div>
      </template>

      <!-- Rename: from key → to key -->
      <template v-else-if="op.op === 'rename'">
        <div class="op-row">
          <a-select
            v-model:value="op.from"
            :options="contextOptions"
            placeholder="from key"
            allow-clear
            show-search
            class="op-flex"
            @change="update()"
          />
          <span class="op-sym">→</span>
          <a-input
            v-model:value="op.to"
            placeholder="to key"
            class="op-flex"
            @change="update()"
          />
        </div>
      </template>

      <a-divider v-if="idx < operations.length - 1" style="margin: 8px 0; border-color: #222;" />
    </div>

    <a-button size="small" class="add-btn" @click="addOp">+ 添加操作</a-button>
    <div class="hint">支持 <span class="code" v-pre>{{变量名}}</span> 插值；Set 类型留空保持字符串</div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, watch } from 'vue'
import { FORM_CTX } from './useFormContext'

interface SetOp    { op: 'set';    key: string; value: string; value_type: string }
interface DeleteOp { op: 'delete'; key: string }
interface RenameOp { op: 'rename'; from: string; to: string }
type Operation = SetOp | DeleteOp | RenameOp

const VALUE_TYPES = ['str', 'int', 'float', 'bool', 'list', 'dict']

const ctx = inject(FORM_CTX)!
const d = ctx.localData

watch(d, (data) => {
  if (!data || data.type !== 'context-edit') return
  if (!Array.isArray(data.params.operations)) data.params.operations = []
}, { immediate: true })

const operations = computed<Operation[]>(() => d.value.params?.operations ?? [])

const contextOptions = computed(() =>
  ctx.contextFields.value.map(f => ({ value: f.name, label: f.name }))
)

function addOp() {
  d.value.params.operations.push({ op: 'set', key: '', value: '', value_type: '' } as SetOp)
  ctx.emitUpdate()
}

function removeOp(idx: number) {
  d.value.params.operations.splice(idx, 1)
  ctx.emitUpdate()
}

function update() { ctx.emitUpdate() }
</script>

<style scoped>
.op-block  { margin-bottom: 4px; }
.op-header { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.op-type-select { flex: 1; }
.op-del    { flex-shrink: 0; padding: 0 4px !important; }
.op-row    { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
.op-key    { width: 90px; flex-shrink: 0; }
.op-val    { flex: 1; min-width: 0; }
.op-vtype  { width: 72px; flex-shrink: 0; }
.op-full   { flex: 1; min-width: 0; }
.op-flex   { flex: 1; min-width: 0; }
.op-sym    { color: #555; font-size: 12px; flex-shrink: 0; }
.add-btn   { width: 100%; margin-top: 4px; color: #555 !important; border-color: #303030 !important; background: transparent !important; font-size: 11px !important; }
.add-btn:hover { color: #888 !important; border-color: #555 !important; }
.hint      { font-size: 11px; color: #444; margin-top: 6px; line-height: 1.5; }
.code      { font-family: 'Consolas', monospace; color: #555; }
</style>
