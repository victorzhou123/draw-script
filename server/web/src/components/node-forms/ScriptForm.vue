<template>
  <div>
    <a-form-item label="引用脚本">
      <a-select v-model:value="d.script_id" :style="{ width: '100%' }" placeholder="选择要调用的脚本"
        allow-clear show-search option-filter-prop="label" @change="onScriptChange">
        <a-select-opt-group v-if="sameProjectScripts.length" :label="sameProjectGroupLabel">
          <a-select-option v-for="s in sameProjectScripts" :key="s.id" :value="s.id" :label="s.name">
            {{ s.name }}
          </a-select-option>
        </a-select-opt-group>
        <a-select-opt-group v-for="g in otherProjectGroups" :key="g.id" :label="g.name">
          <a-select-option v-for="s in g.scripts" :key="s.id" :value="s.id" :label="s.name">
            {{ s.name }}
          </a-select-option>
        </a-select-opt-group>
        <a-select-opt-group v-if="unassignedScripts.length" label="未分配项目组">
          <a-select-option v-for="s in unassignedScripts" :key="s.id" :value="s.id" :label="s.name">
            {{ s.name }}
          </a-select-option>
        </a-select-opt-group>
      </a-select>
    </a-form-item>

    <!-- 入口字段映射 -->
    <div class="section-title">入口字段映射</div>
    <div class="hint-text">
      {{ d.input_mappings?.length ? '仅传入下列字段（父变量名 → 子脚本 Start 字段）' : '未配置，子脚本以空上下文启动' }}
    </div>
    <div v-if="d.script_id && childStartFields.length === 0" class="hint-text warn-text">
      子脚本 Start 节点未定义字段，无法添加入口映射
    </div>
    <div v-for="(m, idx) in d.input_mappings" :key="'in-' + idx" class="mapping-row">
      <a-auto-complete
        v-model:value="m.from"
        :options="inputFromOptions(idx)"
        placeholder="父变量名"
        class="map-field"
        @change="autoFill(m, 'from')"
      />
      <span class="map-arrow">→</span>
      <a-select
        v-model:value="m.to"
        :options="inputToOptions(idx)"
        placeholder="子脚本 Start 字段"
        class="map-field"
        allow-clear
        show-search
        @change="autoFill(m, 'to')"
      />
      <a-button type="text" size="small" danger @click="removeInputMapping(idx)">✕</a-button>
    </div>
    <a-button
      size="small"
      class="add-btn"
      :disabled="d.script_id && childStartFields.length === 0"
      @click="addInputMapping"
    >+ 添加入口映射</a-button>

    <!-- 出口字段映射 -->
    <div class="section-title" style="margin-top: 14px">出口字段映射</div>
    <div class="hint-text">
      {{ d.output_mappings?.length ? '仅写回下列字段（子脚本 End 字段 → 父变量名）' : '未配置，不写回任何字段' }}
    </div>
    <div v-if="d.script_id && childEndFields.length === 0" class="hint-text">
      子脚本 End 节点未配置 return_fields，出口字段需手动输入
    </div>
    <div v-for="(m, idx) in d.output_mappings" :key="'out-' + idx" class="mapping-row">
      <a-auto-complete
        v-if="childEndFields.length === 0"
        v-model:value="m.from"
        placeholder="子脚本字段名"
        class="map-field"
        @change="autoFill(m, 'from')"
      />
      <a-select
        v-else
        v-model:value="m.from"
        :options="outputFromOptions(idx)"
        placeholder="子脚本 End 字段"
        class="map-field"
        allow-clear
        show-search
        @change="autoFill(m, 'from')"
      />
      <span class="map-arrow">→</span>
      <a-auto-complete
        v-model:value="m.to"
        :options="outputToOptions(idx)"
        placeholder="父变量名"
        class="map-field"
        @change="autoFill(m, 'to')"
      />
      <a-button type="text" size="small" danger @click="removeOutputMapping(idx)">✕</a-button>
    </div>
    <a-button size="small" class="add-btn" @click="addOutputMapping">+ 添加出口映射</a-button>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, watch } from 'vue'
import { FORM_CTX } from './useFormContext'
import { useScriptStore } from '@/stores/scriptStore'
import { useProjectStore } from '@/stores/projectStore'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
function update() { ctx.emitUpdate() }

const scriptStore  = useScriptStore()
const projectStore = useProjectStore()

const currentProjectId = computed(() => scriptStore.currentScript?.project_id ?? null)

const sameProjectGroupLabel = computed(() => {
  const p = projectStore.projects.find(p => p.id === currentProjectId.value)
  return p ? `本项目组：${p.name}` : '本项目组'
})

const sameProjectScripts = computed(() => {
  const pid = currentProjectId.value
  if (!pid) return []
  return ctx.otherScripts.value.filter((s: any) => s.project_id === pid)
})

const otherProjectGroups = computed(() => {
  const pid = currentProjectId.value
  const map = new Map<string, { id: string; name: string; scripts: any[] }>()
  for (const s of ctx.otherScripts.value) {
    if (!s.project_id || s.project_id === pid) continue
    if (!map.has(s.project_id)) {
      const p = projectStore.projects.find(p => p.id === s.project_id)
      map.set(s.project_id, { id: s.project_id, name: p?.name ?? s.project_id, scripts: [] })
    }
    map.get(s.project_id)!.scripts.push(s)
  }
  return Array.from(map.values())
})

const unassignedScripts = computed(() => {
  return ctx.otherScripts.value.filter((s: any) => !s.project_id)
})

// ── 解析子脚本 Start/End 字段 ─────────────────────────────────────────────────

const selectedScript = computed(() =>
  ctx.otherScripts.value.find((s: any) => s.id === d.value.script_id) ?? null
)

const childStartFields = computed<string[]>(() => {
  if (!selectedScript.value) return []
  try {
    const flow = JSON.parse(selectedScript.value.flow_json || '{}')
    const startCell = (flow.cells ?? []).find((c: any) => c.data?.type === 'start')
    return (startCell?.data?.fields ?? []).map((f: any) => f.name).filter(Boolean)
  } catch { return [] }
})

const childEndFields = computed<string[]>(() => {
  if (!selectedScript.value) return []
  try {
    const flow = JSON.parse(selectedScript.value.flow_json || '{}')
    const endCell = (flow.cells ?? []).find((c: any) => c.data?.type === 'end')
    return (endCell?.data?.return_fields ?? []).filter(Boolean)
  } catch { return [] }
})

const childStartFieldOptions = computed(() =>
  childStartFields.value.map(n => ({ value: n, label: n }))
)

const childEndFieldOptions = computed(() =>
  childEndFields.value.map(n => ({ value: n, label: n }))
)

const parentVarOptions = computed(() =>
  ctx.contextFields.value.map((f: any) => ({ value: f.name }))
)

function inputFromOptions(idx: number) {
  const used = new Set(d.value.input_mappings.filter((_: any, i: number) => i !== idx).map((m: any) => m.from).filter(Boolean))
  return parentVarOptions.value.filter(o => !used.has(o.value))
}

function inputToOptions(idx: number) {
  const used = new Set(d.value.input_mappings.filter((_: any, i: number) => i !== idx).map((m: any) => m.to).filter(Boolean))
  return childStartFieldOptions.value.filter(o => !used.has(o.value))
}

function outputFromOptions(idx: number) {
  const used = new Set(d.value.output_mappings.filter((_: any, i: number) => i !== idx).map((m: any) => m.from).filter(Boolean))
  return childEndFieldOptions.value.filter(o => !used.has(o.value))
}

function outputToOptions(idx: number) {
  const used = new Set(d.value.output_mappings.filter((_: any, i: number) => i !== idx).map((m: any) => m.to).filter(Boolean))
  return parentVarOptions.value.filter(o => !used.has(o.value))
}

// ── 切换子脚本时清空无效映射 ──────────────────────────────────────────────────

function onScriptChange(scriptId: string | undefined) {
  if (scriptId) {
    const script = ctx.otherScripts.value.find((s: any) => s.id === scriptId)
    if (script) d.value.label = script.name
  }
  d.value.input_mappings = []
  d.value.output_mappings = []
  update()
}

// ── 自动镜像填充 ──────────────────────────────────────────────────────────────

function autoFill(m: { from: string; to: string }, changed: 'from' | 'to') {
  if (changed === 'from' && !m.to) m.to = m.from
  if (changed === 'to'   && !m.from) m.from = m.to
  update()
}

// ── 添加 / 删除 ───────────────────────────────────────────────────────────────

function addInputMapping() {
  d.value.input_mappings.push({ from: '', to: '' })
  update()
}
function removeInputMapping(idx: number) {
  d.value.input_mappings.splice(idx, 1)
  update()
}

function addOutputMapping() {
  d.value.output_mappings.push({ from: '', to: '' })
  update()
}
function removeOutputMapping(idx: number) {
  d.value.output_mappings.splice(idx, 1)
  update()
}
</script>

<style scoped>
.section-title { font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.8px; margin: 14px 0 6px; }
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; line-height: 1.5; }
.warn-text { color: #614700; }
.mapping-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.map-field { flex: 1; min-width: 0; }
.map-arrow { color: #555; font-size: 13px; flex-shrink: 0; }
.add-btn { width: 100%; margin-top: 4px; color: #555 !important; border-color: #303030 !important; background: transparent !important; font-size: 11px !important; }
.add-btn:hover { color: #888 !important; border-color: #555 !important; }
.add-btn:disabled { opacity: 0.4; pointer-events: none; }
</style>
