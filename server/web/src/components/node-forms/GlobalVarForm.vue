<template>
  <div>
    <!-- mode -->
    <a-form-item label="操作模式">
      <a-radio-group v-model:value="d.params.mode" button-style="solid" size="small" @change="update()">
        <a-radio-button value="read">读取</a-radio-button>
        <a-radio-button value="write">写入</a-radio-button>
      </a-radio-group>
    </a-form-item>

    <!-- ── write mode ── -->
    <template v-if="d.params.mode === 'write'">
      <div v-for="(item, idx) in writeItems" :key="idx" class="item-block">
        <div class="item-row">
          <a-auto-complete
            v-model:value="item.var_name"
            :options="varNameOptions"
            placeholder="全局变量名"
            class="item-varname"
            @change="update()"
          />
          <a-button type="text" size="small" danger class="item-del" @click="removeWriteItem(idx)">✕</a-button>
        </div>
        <div class="item-row">
          <a-radio-group v-model:value="item.source_type" button-style="solid" size="small" @change="update()">
            <a-radio-button value="context">Context</a-radio-button>
            <a-radio-button value="literal">固定值</a-radio-button>
          </a-radio-group>
        </div>
        <div class="item-row" v-if="item.source_type === 'context'">
          <a-select
            v-model:value="item.source_key"
            :options="contextOptions"
            placeholder="选择 context 变量"
            allow-clear show-search
            class="item-full"
            @change="onWriteSourceKeyChange(item)"
          />
        </div>
        <div class="item-row" v-else>
          <a-input
            v-model:value="item.literal_value"
            placeholder='字符串或 JSON，如: 42 / true / "hello"'
            class="item-full"
            @change="update()"
          />
        </div>
        <a-divider v-if="idx < writeItems.length - 1" style="margin: 8px 0; border-color: #222;" />
      </div>
      <a-button size="small" class="add-btn" @click="addWriteItem">+ 添加写入项</a-button>
    </template>

    <!-- ── read mode ── -->
    <template v-else>
      <div v-for="(item, idx) in readItems" :key="idx" class="item-block">
        <div class="item-row">
          <a-select
            v-model:value="item.var_name"
            :options="varNameOptions"
            placeholder="选择全局变量"
            allow-clear
            show-search
            class="item-flex"
            @change="onReadVarNameChange(item)"
          />
          <span class="item-arrow">→</span>
          <a-input
            v-model:value="item.target_key"
            :placeholder="item.var_name || 'context key'"
            class="item-flex"
            @change="update()"
          />
          <a-button type="text" size="small" danger class="item-del" @click="removeReadItem(idx)">✕</a-button>
        </div>
        <a-divider v-if="idx < readItems.length - 1" style="margin: 8px 0; border-color: #222;" />
      </div>
      <a-button size="small" class="add-btn" @click="addReadItem">+ 添加读取项</a-button>
      <div class="hint">全局变量名 → 写入 context 的 key（留空与变量名相同）</div>
    </template>

    <!-- ── data panel ── -->
    <a-divider style="margin: 10px 0; border-color: #2a2a2a;" />
    <div class="panel-header" @click="panelOpen = !panelOpen">
      <span class="panel-title">当前数据 <span class="panel-count">({{ allVars.length }})</span></span>
      <span class="panel-arrow">{{ panelOpen ? '▲' : '▼' }}</span>
    </div>

    <template v-if="panelOpen">
      <div v-if="allVars.length === 0 && !adding" class="empty-hint">暂无数据</div>

      <div v-for="v in allVars" :key="v.name" class="var-row">
        <template v-if="editingName === v.name">
          <span class="var-name">{{ v.name }}</span>
          <a-input
            v-model:value="editingValue"
            size="small"
            class="var-val-input"
            @keydown.enter="saveEdit(v.name)"
            @keydown.esc="cancelEdit"
          />
          <a-button type="text" size="small" class="icon-btn ok" @click="saveEdit(v.name)">✓</a-button>
          <a-button type="text" size="small" class="icon-btn" @click="cancelEdit">✕</a-button>
        </template>
        <template v-else>
          <span class="var-name">{{ v.name }}</span>
          <span class="var-val" :title="displayValue(v.value)">{{ displayValue(v.value) }}</span>
          <a-button type="text" size="small" class="icon-btn" @click="startEdit(v)">✏</a-button>
          <a-button type="text" size="small" danger class="icon-btn" @click="deleteVar(v.name)">✕</a-button>
        </template>
      </div>

      <!-- add new row -->
      <div v-if="adding" class="var-row">
        <a-input v-model:value="newName" size="small" placeholder="变量名" class="var-name-input" @keydown.esc="adding = false" />
        <a-input v-model:value="newValue" size="small" placeholder='值（JSON 或字符串）' class="var-val-input" @keydown.enter="saveNew" @keydown.esc="adding = false" />
        <a-button type="text" size="small" class="icon-btn ok" @click="saveNew">✓</a-button>
        <a-button type="text" size="small" class="icon-btn" @click="adding = false">✕</a-button>
      </div>

      <a-button v-if="!adding" size="small" class="add-btn" style="margin-top:6px" @click="startAdd">+ 手动添加</a-button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { FORM_CTX } from './useFormContext'
import { useProjectStore } from '@/stores/projectStore'
import { useScriptStore } from '@/stores/scriptStore'

interface WriteItem {
  var_name: string
  source_type: 'context' | 'literal'
  source_key: string
  literal_value: string
}

interface ReadItem {
  var_name: string
  target_key: string
}

const ctx = inject(FORM_CTX)!
const d = ctx.localData
const projectStore = useProjectStore()
const scriptStore = useScriptStore()

const projectId = computed(() => scriptStore.currentScript?.project_id ?? null)
const allVars = computed(() => projectId.value ? (projectStore.globalVars[projectId.value] ?? []) : [])

watch(d, (data) => {
  if (!data || data.type !== 'global-var') return
  if (!data.params.mode)         data.params.mode = 'read'
  if (!data.params.write_items)  data.params.write_items = []
  if (!data.params.read_items)   data.params.read_items = []
}, { immediate: true })

const writeItems = computed<WriteItem[]>(() => d.value.params?.write_items ?? [])
const readItems  = computed<ReadItem[]>(() => d.value.params?.read_items  ?? [])

const varNameOptions = computed(() =>
  ctx.availableGlobalVars.value.map(name => ({ value: name, label: name }))
)
const contextOptions = computed(() =>
  ctx.contextFields.value.map(f => ({ value: f.name, label: f.name }))
)

function addWriteItem() {
  d.value.params.write_items.push({ var_name: '', source_type: 'context', source_key: '', literal_value: '' })
  ctx.emitUpdate()
}
function removeWriteItem(idx: number) {
  d.value.params.write_items.splice(idx, 1)
  ctx.emitUpdate()
}
function onWriteSourceKeyChange(item: WriteItem) {
  if (!item.var_name) item.var_name = item.source_key
  ctx.emitUpdate()
}

function addReadItem() {
  d.value.params.read_items.push({ var_name: '', target_key: '' })
  ctx.emitUpdate()
}
function removeReadItem(idx: number) {
  d.value.params.read_items.splice(idx, 1)
  ctx.emitUpdate()
}
function onReadVarNameChange(item: ReadItem) {
  if (!item.target_key) item.target_key = item.var_name
  ctx.emitUpdate()
}

function update() { ctx.emitUpdate() }

// ── data panel ──
const panelOpen = ref(true)
const editingName = ref<string | null>(null)
const editingValue = ref('')
const adding = ref(false)
const newName = ref('')
const newValue = ref('')

function displayValue(val: any): string {
  if (val === null || val === undefined) return 'null'
  const s = typeof val === 'string' ? val : JSON.stringify(val)
  return s.length > 40 ? s.slice(0, 38) + '…' : s
}

function startEdit(v: { name: string; value: any }) {
  editingName.value = v.name
  editingValue.value = typeof v.value === 'string' ? v.value : JSON.stringify(v.value)
}

function cancelEdit() {
  editingName.value = null
  editingValue.value = ''
}

async function saveEdit(name: string) {
  if (!projectId.value) return
  let parsed: any
  try { parsed = JSON.parse(editingValue.value) } catch { parsed = editingValue.value }
  await projectStore.upsertGlobalVar(projectId.value, name, parsed)
  cancelEdit()
}

async function deleteVar(name: string) {
  if (!projectId.value) return
  await projectStore.deleteGlobalVar(projectId.value, name)
}

function startAdd() {
  newName.value = ''
  newValue.value = ''
  adding.value = true
}

async function saveNew() {
  if (!projectId.value || !newName.value.trim()) return
  let parsed: any
  try { parsed = JSON.parse(newValue.value) } catch { parsed = newValue.value }
  await projectStore.upsertGlobalVar(projectId.value, newName.value.trim(), parsed)
  adding.value = false
}
</script>

<style scoped>
.item-block  { margin-bottom: 4px; }
.item-row    { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.item-varname { flex: 1; min-width: 0; }
.item-full   { flex: 1; min-width: 0; }
.item-flex   { flex: 1; min-width: 0; }
.item-arrow  { color: #555; font-size: 12px; flex-shrink: 0; }
.item-del    { flex-shrink: 0; padding: 0 4px !important; }
.add-btn     { width: 100%; margin-top: 4px; color: #555 !important; border-color: #303030 !important; background: transparent !important; font-size: 11px !important; }
.add-btn:hover { color: #888 !important; border-color: #555 !important; }
.hint        { font-size: 11px; color: #444; margin-top: 4px; line-height: 1.5; }

.panel-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding: 2px 0 6px; user-select: none; }
.panel-title  { font-size: 11px; color: #666; }
.panel-count  { color: #444; }
.panel-arrow  { font-size: 10px; color: #444; }

.empty-hint { font-size: 11px; color: #3a3a3a; padding: 4px 0; }

.var-row { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
.var-name { font-size: 11px; color: #888; min-width: 80px; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; }
.var-val  { font-size: 11px; color: #555; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; }
.var-name-input { width: 90px; flex-shrink: 0; }
.var-val-input  { flex: 1; min-width: 0; font-size: 11px; }
.icon-btn { flex-shrink: 0; padding: 0 3px !important; font-size: 11px; color: #555 !important; }
.icon-btn.ok { color: #52c41a !important; }
</style>
