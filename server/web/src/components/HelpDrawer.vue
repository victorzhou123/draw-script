<template>
  <a-drawer
    title="帮助文档"
    placement="right"
    :width="560"
    :open="open"
    :body-style="{ padding: 0, background: '#141414' }"
    :header-style="{ background: '#1a1a1a', borderBottom: '1px solid #252525', color: '#e0e0e0' }"
    @close="emit('close')"
  >
    <a-tabs v-model:activeKey="activeTab" class="help-tabs">
      <a-tab-pane key="guide" tab="使用说明">
        <div class="md-body" v-html="guideHtml" />
      </a-tab-pane>
      <a-tab-pane key="api" tab="API 接口">
        <div class="md-body" v-html="apiHtml" />
      </a-tab-pane>
    </a-tabs>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const activeTab = ref('guide')

const GUIDE_MD = `
## 快速开始

1. **新建脚本** — 在左侧"脚本"面板点击 **+**，输入名称后确认。
2. **编辑流程** — 从"节点"面板拖拽节点到画布，连线构成执行流程。
3. **运行脚本** — 在顶部工具栏选择客户端，点击运行；也可通过 API / Webhook 触发。

---

## 节点类型

| 节点 | 说明 |
|------|------|
| **开始 / 结束** | 流程的入口和出口，每个脚本必须有且仅有一个开始节点 |
| **动作** | 在客户端执行鼠标点击、键盘输入、滚动等操作 |
| **条件** | 根据变量或 CV 识别结果分支跳转（真 / 假） |
| **循环** | 固定次数或条件循环，支持嵌套 |
| **延迟** | 等待指定毫秒数后继续 |
| **截图** | 截取当前屏幕并保存到变量 |
| **视觉识别** | 使用 OpenCV / OCR / Qwen-VL 识别图像内容 |
| **HTTP 请求** | 向外部接口发送请求，结果存入变量 |
| **Webhook** | 流程执行到此节点时触发出站 Webhook 通知 |

---

## 变量系统

- 所有节点共享同一个 \`variables\` 字典（执行上下文）。
- 通过 API 或 Webhook 触发时，请求 Body 中的字段会自动注入为初始变量。
- 在节点属性面板中可用 \`{{变量名}}\` 语法引用变量值。

---

## 快捷键

| 操作 | 快捷键 |
|------|--------|
| 撤销 | Ctrl + Z |
| 重做 | Ctrl + Y |
| 删除选中 | Delete / Backspace |
| 全选 | Ctrl + A |
| 复制 | Ctrl + C |
| 粘贴 | Ctrl + V |
| 适应画布 | Ctrl + Shift + H |

---

## 客户端管理

- 客户端（Windows 机器）安装并运行 \`client/start.bat\` 后自动注册到服务端。
- 工具栏右上角绿色数字表示当前在线客户端数量。
- 点击"客户端"可查看详情、所属项目组，以及在线状态。

---

## 项目组

将脚本与客户端归组管理。同一项目组内的脚本可以共享标记点（Marker），用于 CV 识别的坐标定位。
`

const API_MD = `
## 认证

当前版本暂无鉴权，建议部署在内网或通过反向代理添加认证层。

---

## 直接触发脚本

\`\`\`
POST /api/scripts/{script_id}/run
Content-Type: application/json
\`\`\`

**请求体**

\`\`\`json
{
  "client_id": "客户端ID",
  "params": {
    "key1": "value1",
    "key2": 123
  }
}
\`\`\`

**响应**

\`\`\`json
{
  "id": "执行ID",
  "script_id": "...",
  "client_id": "...",
  "status": "running",
  "started_at": "2026-01-01T00:00:00"
}
\`\`\`

\`params\` 中的所有字段会作为初始变量注入脚本执行上下文，脚本节点可通过 \`{{key1}}\` 引用。

---

## Webhook 触发（推荐第三方集成使用）

### 第一步：创建触发器

\`\`\`
POST /api/webhooks
Content-Type: application/json
\`\`\`

\`\`\`json
{
  "name": "my-trigger",
  "script_id": "脚本ID",
  "client_id": "客户端ID",
  "enabled": true
}
\`\`\`

### 第二步：第三方调用

\`\`\`
POST /api/webhooks/receive/{name}
Content-Type: application/json
\`\`\`

\`\`\`json
{
  "order_id": "12345",
  "action": "place_order"
}
\`\`\`

请求 Body 整体作为参数注入脚本变量。

**响应**

\`\`\`json
{
  "received": true,
  "name": "my-trigger",
  "triggered": true,
  "execution_id": "执行ID"
}
\`\`\`

---

## 查询执行状态

\`\`\`
GET /api/scripts/{script_id}/executions
\`\`\`

返回最近 50 条执行记录，包含 \`status\`（running / completed / error / stopped）和日志。

---

## 停止执行

\`\`\`
POST /api/scripts/{script_id}/stop?execution_id={execution_id}
\`\`\`

---

## 客户端列表

\`\`\`
GET /api/clients
\`\`\`

返回所有已注册客户端及其在线状态，\`status\` 字段为 \`connected\` 表示在线。
`

const guideHtml = computed(() => marked.parse(GUIDE_MD) as string)
const apiHtml   = computed(() => marked.parse(API_MD)   as string)
</script>

<style scoped>
.help-tabs {
  height: 100%;
}

:deep(.ant-tabs-nav) {
  background: #1a1a1a;
  border-bottom: 1px solid #252525;
  padding: 0 16px;
  margin: 0;
}

:deep(.ant-tabs-content-holder) {
  overflow-y: auto;
  height: calc(100vh - 110px);
}

.md-body {
  padding: 20px 24px 32px;
  color: #c0c0c0;
  font-size: 13px;
  line-height: 1.8;
}

/* headings */
.md-body :deep(h2) {
  color: #e0e0e0;
  font-size: 15px;
  font-weight: 600;
  margin: 28px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #252525;
}
.md-body :deep(h3) {
  color: #d0d0d0;
  font-size: 13px;
  font-weight: 600;
  margin: 20px 0 8px;
}

/* paragraphs */
.md-body :deep(p) {
  margin: 0 0 10px;
}

/* horizontal rule */
.md-body :deep(hr) {
  border: none;
  border-top: 1px solid #222;
  margin: 20px 0;
}

/* inline code */
.md-body :deep(code) {
  background: #252525;
  border: 1px solid #2e2e2e;
  border-radius: 3px;
  padding: 1px 5px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: #7ec8e3;
}

/* code blocks */
.md-body :deep(pre) {
  background: #1e1e1e;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 12px 16px;
  overflow-x: auto;
  margin: 10px 0 14px;
}
.md-body :deep(pre code) {
  background: transparent;
  border: none;
  padding: 0;
  color: #a8d8a8;
  font-size: 12px;
  line-height: 1.6;
}

/* tables */
.md-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0 14px;
  font-size: 12px;
}
.md-body :deep(th) {
  background: #1e1e1e;
  color: #aaa;
  font-weight: 600;
  padding: 7px 12px;
  text-align: left;
  border: 1px solid #2a2a2a;
}
.md-body :deep(td) {
  padding: 6px 12px;
  border: 1px solid #222;
  vertical-align: top;
}
.md-body :deep(tr:nth-child(even) td) {
  background: #1a1a1a;
}

/* lists */
.md-body :deep(ul), .md-body :deep(ol) {
  padding-left: 20px;
  margin: 0 0 10px;
}
.md-body :deep(li) {
  margin-bottom: 4px;
}

/* bold */
.md-body :deep(strong) {
  color: #e0e0e0;
  font-weight: 600;
}
</style>
