<template>
  <a-drawer
    title="AI 模型管理"
    :open="open"
    :width="520"
    placement="right"
    @close="emit('close')"
  >
    <a-tabs v-model:activeKey="tabKey">
      <!-- ── 本地模型 ─────────────────────────────────── -->
      <a-tab-pane key="local" tab="本地模型">
        <div class="model-card">
          <div class="model-card-header">
            <div class="model-card-title">
              <span class="model-icon local-icon">🖥</span>
              <span class="model-name">PaddleOCR (CPU)</span>
            </div>
            <a-tag :color="ocrTagColor">{{ ocrStatusText }}</a-tag>
          </div>
          <p class="model-desc">基于飞桨的 OCR 识别引擎，支持中英文文字识别，在 Vision 节点中作为 OCR 后端使用。</p>
          <div class="model-card-footer">
            <a-button
              v-if="!ocrStatus?.loaded"
              size="small"
              :loading="ocrInitializing"
              :disabled="ocrInitializing"
              @click="handleInitOCR"
            >
              {{ ocrInitializing ? '加载中…' : '初始化' }}
            </a-button>
            <a-button
              v-else
              size="small"
              :loading="ocrInitializing"
              :disabled="ocrInitializing"
              @click="handleReinitOCR"
            >
              {{ ocrInitializing ? '加载中…' : '重新初始化' }}
            </a-button>
            <a-button size="small" class="secondary-btn" @click="refreshOCRStatus">
              刷新状态
            </a-button>
          </div>
          <div v-if="ocrStatus?.error" class="error-text">{{ ocrStatus.error }}</div>
        </div>
      </a-tab-pane>

      <!-- ── 第三方模型 ───────────────────────────────── -->
      <a-tab-pane key="third_party" tab="第三方模型">
        <div class="tab-toolbar">
          <a-button type="primary" size="small" @click="openAddModal">+ 添加模型</a-button>
        </div>

        <div v-if="modelStore.thirdPartyModels.length === 0" class="empty-hint">
          暂无第三方模型配置，点击上方按钮添加
        </div>

        <div v-for="m in modelStore.thirdPartyModels" :key="m.id" class="model-card">
          <div class="model-card-header">
            <div class="model-card-title">
              <span class="model-icon" :class="m.provider === 'qwen' ? 'qwen-icon' : 'glm-icon'">
                {{ m.provider === 'qwen' ? 'Q' : 'G' }}
              </span>
              <div>
                <div class="model-name">{{ m.name }}</div>
                <div class="model-provider">{{ PROVIDER_LABELS[m.provider] ?? m.provider }}</div>
              </div>
            </div>
            <a-tag :color="m.enabled ? 'green' : 'default'">{{ m.enabled ? '已启用' : '已禁用' }}</a-tag>
          </div>

          <div class="model-meta">
            <span class="meta-item">
              <span class="meta-label">模型:</span> {{ m.model_name || '未配置' }}
            </span>
            <span class="meta-item">
              <span class="meta-label">API Key:</span>
              {{ m.api_key ? maskKey(m.api_key) : '未配置' }}
            </span>
          </div>

          <!-- 卡片测试结果 -->
          <div v-if="cardTestResults[m.id]" class="card-test-result" :class="cardTestResults[m.id].success ? 'test-ok' : 'test-fail'">
            <span class="test-icon">{{ cardTestResults[m.id].success ? '✓' : '✕' }}</span>
            {{ cardTestResults[m.id].message }}
            <span v-if="cardTestResults[m.id].latency_ms !== null" class="test-latency">
              {{ cardTestResults[m.id].latency_ms }}ms
            </span>
          </div>

          <div class="model-card-footer">
            <a-button
              size="small"
              :loading="cardTesting[m.id]"
              @click="handleCardTest(m)"
            >
              测试连接
            </a-button>
            <a-button size="small" @click="openEditModal(m)">编辑</a-button>
            <a-popconfirm
              title="确认删除此模型配置？"
              ok-text="删除"
              cancel-text="取消"
              @confirm="handleDelete(m.id)"
            >
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- ── 添加 / 编辑 弹窗 ───────────────────────────── -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingModel ? '编辑模型配置' : '添加第三方模型'"
      :confirm-loading="saving"
      ok-text="保存"
      cancel-text="取消"
      @ok="handleSave"
      @cancel="closeModal"
    >
      <a-form layout="vertical" size="small" :model="form">
        <a-form-item label="显示名称" required>
          <a-input v-model:value="form.name" placeholder="例如：通义千问 VL" />
        </a-form-item>
        <a-form-item label="服务商" required>
          <a-select v-model:value="form.provider" :disabled="!!editingModel" @change="onProviderChange">
            <a-select-option value="qwen">Qwen（通义千问）</a-select-option>
            <a-select-option value="glm">GLM（智谱 AI）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="API Key" required>
          <a-input-password v-model:value="form.api_key" placeholder="sk-..." />
        </a-form-item>
        <a-form-item label="模型名称">
          <a-input v-model:value="form.model_name" :placeholder="MODEL_DEFAULTS[form.provider] ?? ''" />
          <div class="field-hint">
            <span v-if="form.provider === 'qwen'">推荐：qwen-vl-plus / qwen-vl-max</span>
            <span v-else-if="form.provider === 'glm'">推荐：glm-4v / glm-4v-plus</span>
          </div>
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input v-model:value="form.base_url" :placeholder="BASE_URL_DEFAULTS[form.provider] ?? ''" />
          <div class="field-hint">留空则使用默认地址</div>
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>

        <!-- 弹窗内连接测试 -->
        <a-form-item style="margin-bottom: 0">
          <div class="modal-test-row">
            <a-button size="small" :loading="modalTesting" @click="handleModalTest">
              测试连接
            </a-button>
            <div v-if="modalTestResult" class="modal-test-result" :class="modalTestResult.success ? 'test-ok' : 'test-fail'">
              <span class="test-icon">{{ modalTestResult.success ? '✓' : '✕' }}</span>
              {{ modalTestResult.message }}
              <span v-if="modalTestResult.latency_ms !== null" class="test-latency">
                {{ modalTestResult.latency_ms }}ms
              </span>
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useModelStore } from '@/stores/modelStore'
import { api, type AIModel, type ModelTestResult, type OCRStatus } from '@/services/api'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const tabKey = ref('local')
const modelStore = useModelStore()

// ── OCR status ──────────────────────────────────────────────────────
const ocrStatus = ref<OCRStatus | null>(null)
const ocrInitializing = ref(false)

const ocrTagColor = ref('default')
const ocrStatusText = ref('检测中…')

function updateOCRDisplay() {
  const s = ocrStatus.value
  if (!s) { ocrTagColor.value = 'default'; ocrStatusText.value = '检测中…'; return }
  if (s.error)     { ocrTagColor.value = 'red';    ocrStatusText.value = '加载失败'; return }
  if (s.loaded)    { ocrTagColor.value = 'green';  ocrStatusText.value = '已加载';   return }
  if (s.loading)   { ocrTagColor.value = 'blue';   ocrStatusText.value = '加载中…';  return }
  if (s.installed) { ocrTagColor.value = 'orange'; ocrStatusText.value = '已安装 / 未加载'; return }
  ocrTagColor.value = 'red'; ocrStatusText.value = '未安装'
}

async function refreshOCRStatus() {
  try {
    const res = await api.getLocalModelStatus()
    ocrStatus.value = res.paddleocr
    updateOCRDisplay()
    if (ocrStatus.value?.loading) {
      ocrInitializing.value = true
      setTimeout(refreshOCRStatus, 2000)
    } else {
      ocrInitializing.value = false
    }
  } catch { /* ignore */ }
}

async function handleInitOCR() {
  ocrInitializing.value = true
  try {
    await api.initLocalModel()
    message.info('正在初始化 PaddleOCR，请稍候…')
    setTimeout(refreshOCRStatus, 2000)
  } catch {
    ocrInitializing.value = false
    message.error('初始化请求失败')
  }
}

async function handleReinitOCR() {
  ocrInitializing.value = true
  try {
    await api.reinitLocalModel()
    message.info('正在重新初始化 PaddleOCR，请稍候…')
    setTimeout(refreshOCRStatus, 2000)
  } catch {
    ocrInitializing.value = false
    message.error('重新初始化请求失败')
  }
}

// ── Card-level connection test ───────────────────────────────────────
const cardTesting = ref<Record<string, boolean>>({})
const cardTestResults = ref<Record<string, ModelTestResult>>({})

async function handleCardTest(m: AIModel) {
  cardTesting.value[m.id] = true
  delete cardTestResults.value[m.id]
  try {
    const result = await api.testSavedModel(m.id)
    cardTestResults.value[m.id] = result
  } catch {
    cardTestResults.value[m.id] = { success: false, message: '请求失败', latency_ms: null }
  } finally {
    cardTesting.value[m.id] = false
  }
}

// ── Modal form ───────────────────────────────────────────────────────
const PROVIDER_LABELS: Record<string, string> = {
  qwen: '通义千问（Dashscope）',
  glm:  '智谱 AI（ZhipuAI）',
}
const MODEL_DEFAULTS: Record<string, string> = {
  qwen: 'qwen-vl-plus',
  glm:  'glm-4v',
}
const BASE_URL_DEFAULTS: Record<string, string> = {
  qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  glm:  'https://open.bigmodel.cn/api/paas/v4',
}

const modalVisible = ref(false)
const editingModel = ref<AIModel | null>(null)
const saving = ref(false)
const modalTesting = ref(false)
const modalTestResult = ref<ModelTestResult | null>(null)

const form = ref({
  name:       '',
  provider:   'qwen' as 'qwen' | 'glm',
  api_key:    '',
  model_name: '',
  base_url:   '',
  enabled:    true,
})

function maskKey(key: string) {
  if (key.length <= 8) return '****'
  return key.slice(0, 4) + '****' + key.slice(-4)
}

function onProviderChange() {
  if (!form.value.model_name) form.value.model_name = MODEL_DEFAULTS[form.value.provider] ?? ''
  if (!form.value.base_url)   form.value.base_url   = BASE_URL_DEFAULTS[form.value.provider] ?? ''
  modalTestResult.value = null
}

function openAddModal() {
  editingModel.value = null
  modalTestResult.value = null
  form.value = {
    name: '', provider: 'qwen',
    api_key: '',
    model_name: MODEL_DEFAULTS['qwen'],
    base_url:   BASE_URL_DEFAULTS['qwen'],
    enabled: true,
  }
  modalVisible.value = true
}

function openEditModal(m: AIModel) {
  editingModel.value = m
  modalTestResult.value = null
  form.value = {
    name:       m.name,
    provider:   m.provider as 'qwen' | 'glm',
    api_key:    m.api_key,
    model_name: m.model_name,
    base_url:   m.base_url,
    enabled:    m.enabled,
  }
  modalVisible.value = true
}

function closeModal() {
  modalVisible.value = false
  editingModel.value = null
  modalTestResult.value = null
}

// Clear test result when form inputs change
watch(
  () => [form.value.api_key, form.value.base_url, form.value.model_name],
  () => { modalTestResult.value = null },
)

async function handleModalTest() {
  if (!form.value.api_key.trim()) { message.warning('请先填写 API Key'); return }
  modalTesting.value = true
  modalTestResult.value = null
  try {
    modalTestResult.value = await api.testModelCredentials({
      api_key:    form.value.api_key,
      base_url:   form.value.base_url || BASE_URL_DEFAULTS[form.value.provider],
      model_name: form.value.model_name || MODEL_DEFAULTS[form.value.provider],
    })
  } catch {
    modalTestResult.value = { success: false, message: '请求失败', latency_ms: null }
  } finally {
    modalTesting.value = false
  }
}

async function handleSave() {
  if (!form.value.name.trim())    { message.warning('请填写显示名称'); return }
  if (!form.value.api_key.trim()) { message.warning('请填写 API Key');  return }
  saving.value = true
  try {
    if (editingModel.value) {
      await modelStore.updateModel(editingModel.value.id, {
        name:       form.value.name,
        api_key:    form.value.api_key,
        model_name: form.value.model_name,
        base_url:   form.value.base_url,
        enabled:    form.value.enabled,
      })
      message.success('已更新')
    } else {
      await modelStore.createModel({
        type:       'third_party',
        provider:   form.value.provider,
        name:       form.value.name,
        api_key:    form.value.api_key,
        model_name: form.value.model_name,
        base_url:   form.value.base_url,
        enabled:    form.value.enabled,
      })
      message.success('已添加')
    }
    closeModal()
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: string) {
  try {
    await modelStore.deleteModel(id)
    delete cardTestResults.value[id]
    message.success('已删除')
  } catch {
    message.error('删除失败')
  }
}

// Load data when drawer opens
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      modelStore.fetchModels()
      refreshOCRStatus()
    }
  },
)
</script>

<style scoped>
.tab-toolbar { margin-bottom: 14px; }

.model-card {
  background: #1e1e1e;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.model-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.model-card-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.model-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.local-icon { background: #162312; border: 1px solid #274916; font-size: 18px; }
.qwen-icon  { background: #111d2c; border: 1px solid #1d3c6b; color: #4096ff; }
.glm-icon   { background: #1a0a2e; border: 1px solid #391085; color: #9254de; }

.model-name     { font-size: 13px; font-weight: 600; color: #d9d9d9; }
.model-provider { font-size: 11px; color: #555; margin-top: 1px; }

.model-desc {
  font-size: 12px;
  color: #555;
  margin: 0 0 10px;
  line-height: 1.6;
}

.model-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}
.meta-item  { font-size: 12px; color: #666; }
.meta-label { color: #444; margin-right: 4px; }

/* Card test result strip */
.card-test-result {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 5px 8px;
  border-radius: 4px;
  margin-bottom: 10px;
}
.test-ok   { background: #162312; border: 1px solid #274916; color: #52c41a; }
.test-fail { background: #2a1215; border: 1px solid #58181c; color: #ff4d4f; }
.test-icon { font-weight: 700; flex-shrink: 0; }
.test-latency { margin-left: auto; font-size: 11px; opacity: 0.7; }

.model-card-footer { display: flex; gap: 8px; }
.secondary-btn { color: #555 !important; }

.error-text {
  font-size: 11px;
  color: #ff4d4f;
  margin-top: 8px;
  word-break: break-all;
}

.empty-hint {
  font-size: 12px;
  color: #444;
  text-align: center;
  padding: 32px 0;
}

/* Modal test row */
.modal-test-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.modal-test-result {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
}

.field-hint { font-size: 11px; color: #444; margin-top: 3px; }
</style>
