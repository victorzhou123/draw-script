<template>
  <div>
    <a-form-item label="观察字段（留空=全部）">
      <a-select
        v-model:value="d.params.fields"
        mode="tags"
        :options="fieldOptions"
        placeholder="输入或选择变量名，留空则打印所有"
        @change="update()"
      />
    </a-form-item>

    <!-- Snapshot visualization -->
    <div v-if="snapshotEntries.length > 0" class="snapshot-section">
      <div class="snapshot-header">最近快照</div>
      <div
        v-for="entry in snapshotEntries"
        :key="entry.clientId"
        class="snapshot-client-block"
      >
        <div v-if="snapshotEntries.length > 1" class="snapshot-client-label">
          <span class="client-dot" />
          {{ entry.clientName }}
        </div>
        <div class="snapshot-fields">
          <div
            v-for="(value, key) in entry.snapshot"
            :key="key"
            class="snapshot-field"
          >
            <span class="snapshot-key">{{ key }}</span>
            <template v-if="isImageField(String(key), value)">
              <img
                :src="toImgSrc(value as string)"
                class="snapshot-img"
                alt=""
              />
            </template>
            <template v-else>
              <span class="snapshot-value">{{ formatValue(value) }}</span>
            </template>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="ctx.nodeId.value" class="snapshot-empty">
      尚无快照数据，执行后显示
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { FORM_CTX } from './useFormContext'
import { useExecutionStore } from '@/stores/executionStore'
import { useClientStore } from '@/stores/clientStore'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const executionStore = useExecutionStore()
const clientStore = useClientStore()

const fieldOptions = computed(() =>
  ctx.contextFields.value.map(f => ({ label: f.name, value: f.name }))
)

function update() { ctx.emitUpdate() }

const snapshotEntries = computed(() => {
  const nodeId = ctx.nodeId.value
  if (!nodeId) return []
  const byClient = executionStore.watchSnapshots[nodeId]
  if (!byClient) return []
  return Object.entries(byClient).map(([clientId, snapshot]) => ({
    clientId,
    clientName: clientStore.clients.find(c => c.id === clientId)?.name ?? clientId,
    snapshot,
  }))
})

function isImageField(key: string, value: unknown): boolean {
  return key.startsWith('image') && typeof value === 'string' && value.length > 0
}

function toImgSrc(value: string): string {
  if (value.startsWith('data:')) return value
  return `data:image/png;base64,${value}`
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
</script>

<style scoped>
.snapshot-section {
  margin-top: 4px;
  border-top: 1px solid #2a2a2a;
  padding-top: 10px;
}

.snapshot-header {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.snapshot-client-block {
  margin-bottom: 10px;
}

.snapshot-client-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #888;
  margin-bottom: 6px;
}

.client-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #1890ff;
  flex-shrink: 0;
}

.snapshot-fields {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.snapshot-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.snapshot-key {
  font-size: 11px;
  color: #888;
  font-family: monospace;
}

.snapshot-value {
  font-size: 12px;
  color: #ccc;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  background: #1a1a1a;
  border-radius: 3px;
  padding: 3px 6px;
  max-height: 80px;
  overflow-y: auto;
}

.snapshot-img {
  max-width: 100%;
  border-radius: 4px;
  border: 1px solid #333;
}

.snapshot-empty {
  font-size: 12px;
  color: #444;
  text-align: center;
  padding: 12px 0 4px;
}
</style>
