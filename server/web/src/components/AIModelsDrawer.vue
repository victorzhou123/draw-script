<template>
  <a-drawer
    title="配置中心"
    :open="open"
    :width="520"
    placement="right"
    @close="emit('close')"
  >
    <a-tabs v-model:activeKey="tabKey">
      <!-- ── AI 配置 ─────────────────────────────────── -->
      <a-tab-pane key="ai_local" tab="本地模型">
        <div class="model-card">
          <div class="model-card-header">
            <div class="model-card-title">
              <span class="model-icon local-icon">🖥</span>
              <span class="model-name">PaddleOCR (CPU)</span>
            </div>
            <a-tag :color="ocrTagColor">{{ ocrStatusText }}</a-tag>
          </div>
          <p class="model-desc">基于飞桨的 OCR 识别引擎，支持中英文文字识别，在 Vision 节点中作为 OCR 后端使用。</p>

          <div class="variant-selector">
            <span class="variant-label">模型版本</span>
            <a-radio-group v-model:value="selectedVariant" size="small" :disabled="ocrInitializing">
              <a-radio-button value="mobile">
                <span>轻量版</span>
                <span class="variant-hint">PP-OCRv4 · 快速</span>
              </a-radio-button>
              <a-radio-button value="server">
                <span>精准版</span>
                <span class="variant-hint">PP-OCRv5 · 高精度</span>
              </a-radio-button>
            </a-radio-group>
            <div v-if="ocrStatus?.loaded" class="variant-current">
              当前已加载：{{ ocrStatus.variant === 'server' ? '精准版 (PP-OCRv5)' : '轻量版 (PP-OCRv4)' }}
            </div>
          </div>

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
              {{ ocrInitializing ? '加载中…' : '切换 / 重新加载' }}
            </a-button>
            <a-button size="small" class="secondary-btn" @click="refreshOCRStatus">
              刷新状态
            </a-button>
          </div>
          <div v-if="ocrStatus?.error" class="error-text">{{ ocrStatus.error }}</div>
        </div>
      </a-tab-pane>

      <a-tab-pane key="ai_third" tab="第三方 AI 模型">
        <div class="tab-toolbar">
          <a-button type="primary" size="small" @click="openAddModelModal">+ 添加模型</a-button>
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

          <div v-if="cardTestResults[m.id]" class="card-test-result" :class="cardTestResults[m.id].success ? 'test-ok' : 'test-fail'">
            <span class="test-icon">{{ cardTestResults[m.id].success ? '✓' : '✕' }}</span>
            {{ cardTestResults[m.id].message }}
            <span v-if="cardTestResults[m.id].latency_ms !== null" class="test-latency">
              {{ cardTestResults[m.id].latency_ms }}ms
            </span>
          </div>

          <div class="model-card-footer">
            <a-button size="small" :loading="cardTesting[m.id]" @click="handleCardTest(m)">测试连接</a-button>
            <a-button size="small" @click="openEditModelModal(m)">编辑</a-button>
            <a-popconfirm title="确认删除此模型配置？" ok-text="删除" cancel-text="取消" @confirm="handleDeleteModel(m.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </div>
        </div>
      </a-tab-pane>

      <!-- ── API & Key 管理 ──────────────────────────── -->
      <a-tab-pane key="api_keys" tab="API & Key">
        <div class="tab-toolbar">
          <a-button type="primary" size="small" @click="openAddKeyModal">+ 添加服务</a-button>
        </div>

        <div v-if="serviceKeyStore.keys.length === 0" class="empty-hint">
          暂无 API Key 配置，点击上方按钮添加（如 Firecrawl、其他第三方服务）
        </div>

        <div v-for="k in serviceKeyStore.keys" :key="k.id" class="model-card">
          <div class="model-card-header">
            <div class="model-card-title">
              <span class="model-icon svc-icon">🔑</span>
              <div class="model-name">{{ k.service_name }}</div>
            </div>
          </div>

          <div class="model-meta">
            <span class="meta-item">
              <span class="meta-label">API Key:</span>
              {{ k.api_key ? maskKey(k.api_key) : '未配置' }}
            </span>
            <span v-if="k.base_url" class="meta-item">
              <span class="meta-label">Base URL:</span>
              <span class="url-text">{{ k.base_url }}</span>
            </span>
          </div>

          <div class="model-card-footer">
            <a-button size="small" @click="openEditKeyModal(k)">编辑</a-button>
            <a-popconfirm title="确认删除此服务配置？" ok-text="删除" cancel-text="取消" @confirm="handleDeleteKey(k.id)">
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- ── AI 模型 添加/编辑 弹窗 ───────────────────── -->
    <a-modal
      v-model:open="modelModalVisible"
      :title="editingModel ? '编辑模型配置' : '添加第三方模型'"
      :confirm-loading="modelSaving"
      ok-text="保存"
      cancel-text="取消"
      @ok="handleSaveModel"
      @cancel="closeModelModal"
    >
      <a-form layout="vertical" size="small" :model="modelForm">
        <a-form-item label="显示名称" required>
          <a-input v-model:value="modelForm.name" placeholder="例如：通义千问 VL" />
        </a-form-item>
        <a-form-item label="服务商" required>
          <a-select v-model:value="modelForm.provider" :disabled="!!editingModel" @change="onProviderChange">
            <a-select-option value="qwen">Qwen（通义千问）</a-select-option>
            <a-select-option value="glm">GLM（智谱 AI）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="API Key" required>
          <a-input-password v-model:value="modelForm.api_key" placeholder="sk-..." />
        </a-form-item>
        <a-form-item label="模型名称">
          <a-input v-model:value="modelForm.model_name" :placeholder="MODEL_DEFAULTS[modelForm.provider] ?? ''" />
          <div class="field-hint">
            <span v-if="modelForm.provider === 'qwen'">推荐：qwen-vl-plus / qwen-vl-max</span>
            <span v-else-if="modelForm.provider === 'glm'">推荐：glm-4v / glm-4v-plus</span>
          </div>
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input v-model:value="modelForm.base_url" :placeholder="BASE_URL_DEFAULTS[modelForm.provider] ?? ''" />
          <div class="field-hint">留空则使用默认地址</div>
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="modelForm.enabled" />
        </a-form-item>
        <a-form-item style="margin-bottom: 0">
          <div class="modal-test-row">
            <a-button size="small" :loading="modalTesting" @click="handleModalTest">测试连接</a-button>
            <div v-if="modalTestResult" class="modal-test-result" :class="modalTestResult.success ? 'test-ok' : 'test-fail'">
              <span class="test-icon">{{ modalTestResult.success ? '✓' : '✕' }}</span>
              {{ modalTestResult.message }}
              <span v-if="modalTestResult.latency_ms !== null" class="test-latency">{{ modalTestResult.latency_ms }}ms</span>
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ── API Key 添加/编辑 弹窗 ────────────────────── -->
    <a-modal
      v-model:open="keyModalVisible"
      :title="editingKey ? '编辑服务配置' : '添加服务 API Key'"
      :confirm-loading="keySaving"
      ok-text="保存"
      cancel-text="取消"
      @ok="handleSaveKey"
      @cancel="closeKeyModal"
    >
      <a-form layout="vertical" size="small" :model="keyForm">
        <a-form-item label="服务名称" required>
          <a-input v-model:value="keyForm.service_name" placeholder="例如：Firecrawl、自建爬虫服务" />
        </a-form-item>
        <a-form-item label="API Key">
          <a-input-password v-model:value="keyForm.api_key" placeholder="fc-..." />
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input v-model:value="keyForm.base_url" placeholder="留空使用默认地址（如 Firecrawl 官方）" />
          <div class="field-hint">自建 Firecrawl 填写自己的部署地址</div>
        </a-form-item>
      </a-form>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useModelStore } from '@/stores/modelStore'
import { useServiceKeyStore } from '@/stores/serviceKeyStore'
import { api, type AIModel, type ModelTestResult, type OCRStatus, type ServiceApiKey } from '@/services/api'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const tabKey = ref('ai_local')
const modelStore = useModelStore()
const serviceKeyStore = useServiceKeyStore()

// ── OCR status ──────────────────────────────────────────────────────
const ocrStatus = ref<OCRStatus | null>(null)
const ocrInitializing = ref(false)
const selectedVariant = ref<'mobile' | 'server'>('mobile')
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
    if (res.paddleocr?.variant) selectedVariant.value = res.paddleocr.variant
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
    await api.initLocalModel(selectedVariant.value)
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
    await api.reinitLocalModel(selectedVariant.value)
    message.info('正在重新初始化 PaddleOCR，请稍候…')
    setTimeout(refreshOCRStatus, 2000)
  } catch {
    ocrInitializing.value = false
    message.error('重新初始化请求失败')
  }
}

// ── AI Model card test ───────────────────────────────────────────────
const cardTesting = ref<Record<string, boolean>>({})
const cardTestResults = ref<Record<string, ModelTestResult>>({})

async function handleCardTest(m: AIModel) {
  cardTesting.value[m.id] = true
  delete cardTestResults.value[m.id]
  try {
    cardTestResults.value[m.id] = await api.testSavedModel(m.id)
  } catch {
    cardTestResults.value[m.id] = { success: false, message: '请求失败', latency_ms: null }
  } finally {
    cardTesting.value[m.id] = false
  }
}

// ── AI Model modal form ──────────────────────────────────────────────
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

const modelModalVisible = ref(false)
const editingModel = ref<AIModel | null>(null)
const modelSaving = ref(false)
const modalTesting = ref(false)
const modalTestResult = ref<ModelTestResult | null>(null)

const modelForm = ref({
  name: '', provider: 'qwen' as 'qwen' | 'glm',
  api_key: '', model_name: '', base_url: '', enabled: true,
})

function maskKey(key: string) {
  if (key.length <= 8) return '****'
  return key.slice(0, 4) + '****' + key.slice(-4)
}

function onProviderChange() {
  if (!modelForm.value.model_name) modelForm.value.model_name = MODEL_DEFAULTS[modelForm.value.provider] ?? ''
  if (!modelForm.value.base_url)   modelForm.value.base_url   = BASE_URL_DEFAULTS[modelForm.value.provider] ?? ''
  modalTestResult.value = null
}

function openAddModelModal() {
  editingModel.value = null
  modalTestResult.value = null
  modelForm.value = {
    name: '', provider: 'qwen',
    api_key: '',
    model_name: MODEL_DEFAULTS['qwen'],
    base_url:   BASE_URL_DEFAULTS['qwen'],
    enabled: true,
  }
  modelModalVisible.value = true
}

function openEditModelModal(m: AIModel) {
  editingModel.value = m
  modalTestResult.value = null
  modelForm.value = {
    name: m.name, provider: m.provider as 'qwen' | 'glm',
    api_key: m.api_key, model_name: m.model_name, base_url: m.base_url, enabled: m.enabled,
  }
  modelModalVisible.value = true
}

function closeModelModal() {
  modelModalVisible.value = false
  editingModel.value = null
  modalTestResult.value = null
}

watch(
  () => [modelForm.value.api_key, modelForm.value.base_url, modelForm.value.model_name],
  () => { modalTestResult.value = null },
)

async function handleModalTest() {
  if (!modelForm.value.api_key.trim()) { message.warning('请先填写 API Key'); return }
  modalTesting.value = true
  modalTestResult.value = null
  try {
    modalTestResult.value = await api.testModelCredentials({
      api_key:    modelForm.value.api_key,
      base_url:   modelForm.value.base_url || BASE_URL_DEFAULTS[modelForm.value.provider],
      model_name: modelForm.value.model_name || MODEL_DEFAULTS[modelForm.value.provider],
    })
  } catch {
    modalTestResult.value = { success: false, message: '请求失败', latency_ms: null }
  } finally {
    modalTesting.value = false
  }
}

async function handleSaveModel() {
  if (!modelForm.value.name.trim())    { message.warning('请填写显示名称'); return }
  if (!modelForm.value.api_key.trim()) { message.warning('请填写 API Key');  return }
  modelSaving.value = true
  try {
    if (editingModel.value) {
      await modelStore.updateModel(editingModel.value.id, {
        name: modelForm.value.name, api_key: modelForm.value.api_key,
        model_name: modelForm.value.model_name, base_url: modelForm.value.base_url,
        enabled: modelForm.value.enabled,
      })
      message.success('已更新')
    } else {
      await modelStore.createModel({
        type: 'third_party', provider: modelForm.value.provider,
        name: modelForm.value.name, api_key: modelForm.value.api_key,
        model_name: modelForm.value.model_name, base_url: modelForm.value.base_url,
        enabled: modelForm.value.enabled,
      })
      message.success('已添加')
    }
    closeModelModal()
  } catch {
    message.error('保存失败')
  } finally {
    modelSaving.value = false
  }
}

async function handleDeleteModel(id: string) {
  try {
    await modelStore.deleteModel(id)
    delete cardTestResults.value[id]
    message.success('已删除')
  } catch {
    message.error('删除失败')
  }
}

// ── Service Key modal form ───────────────────────────────────────────
const keyModalVisible = ref(false)
const editingKey = ref<ServiceApiKey | null>(null)
const keySaving = ref(false)
const keyForm = ref({ service_name: '', api_key: '', base_url: '' })

function openAddKeyModal() {
  editingKey.value = null
  keyForm.value = { service_name: '', api_key: '', base_url: '' }
  keyModalVisible.value = true
}

function openEditKeyModal(k: ServiceApiKey) {
  editingKey.value = k
  keyForm.value = { service_name: k.service_name, api_key: k.api_key, base_url: k.base_url }
  keyModalVisible.value = true
}

function closeKeyModal() {
  keyModalVisible.value = false
  editingKey.value = null
}

async function handleSaveKey() {
  if (!keyForm.value.service_name.trim()) { message.warning('请填写服务名称'); return }
  keySaving.value = true
  try {
    if (editingKey.value) {
      await serviceKeyStore.updateKey(editingKey.value.id, {
        service_name: keyForm.value.service_name,
        api_key: keyForm.value.api_key,
        base_url: keyForm.value.base_url,
      })
      message.success('已更新')
    } else {
      await serviceKeyStore.createKey({
        service_name: keyForm.value.service_name,
        api_key: keyForm.value.api_key,
        base_url: keyForm.value.base_url,
      })
      message.success('已添加')
    }
    closeKeyModal()
  } catch {
    message.error('保存失败')
  } finally {
    keySaving.value = false
  }
}

async function handleDeleteKey(id: string) {
  try {
    await serviceKeyStore.deleteKey(id)
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
      serviceKeyStore.fetchKeys()
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
.svc-icon   { background: #1a1200; border: 1px solid #3d2e00; font-size: 16px; }

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
.url-text   { word-break: break-all; }

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

.variant-selector { margin-bottom: 12px; }
.variant-label {
  display: block;
  font-size: 11px;
  color: #555;
  margin-bottom: 6px;
}
.variant-hint {
  display: block;
  font-size: 10px;
  color: #666;
  line-height: 1.2;
  margin-top: 1px;
}
.variant-current {
  margin-top: 6px;
  font-size: 11px;
  color: #52c41a;
}

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
