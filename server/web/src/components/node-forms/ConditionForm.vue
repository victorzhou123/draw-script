<template>
  <div>
    <a-form-item label="条件类型">
      <a-select v-model:value="d.condition_type" @change="update()">
        <a-select-option value="vision_found">识别是否找到</a-select-option>
        <a-select-option value="vision_text_contains">识别文字包含</a-select-option>
        <a-select-option value="variable_compare">变量比较</a-select-option>
        <a-select-option value="http_status">HTTP状态码</a-select-option>
        <a-select-option value="boolean_check">布尔值判断</a-select-option>
      </a-select>
    </a-form-item>
    <template v-if="d.condition_type === 'vision_text_contains'">
      <a-form-item label="包含文字">
        <a-input v-model:value="d.params.value" @change="update()" />
      </a-form-item>
    </template>
    <template v-if="d.condition_type === 'boolean_check'">
      <a-form-item label="变量路径">
        <a-auto-complete v-model:value="d.params.variable" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))"
          placeholder="例如: last_vision_result.found" allow-clear @change="update()">
          <template #option="{ value: val }">
            <span class="ctx-dot" :class="ctx.contextFields.value.find((f:any) => f.name === val)?.certain ? 'certain' : 'conditional'" />
            {{ val }}
          </template>
        </a-auto-complete>
        <div v-if="!ctx.contextFields.value.length" class="hint-text" style="margin-top:4px">当前节点上游暂无 context 变量</div>
        <div class="hint-text" style="margin-top:4px">判断该变量的值是否为真（非空、非零、非False）</div>
      </a-form-item>
    </template>
    <template v-if="d.condition_type === 'variable_compare'">
      <a-form-item label="变量路径">
        <a-auto-complete v-model:value="d.params.variable" :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))"
          placeholder="last_http_response.status_code" allow-clear @change="update()">
          <template #option="{ value: val }">
            <span class="ctx-dot" :class="ctx.contextFields.value.find((f:any) => f.name === val)?.certain ? 'certain' : 'conditional'" />
            {{ val }}
          </template>
        </a-auto-complete>
        <div v-if="!ctx.contextFields.value.length" class="hint-text" style="margin-top:4px">当前节点上游暂无 context 变量</div>
      </a-form-item>
      <a-form-item label="运算符">
        <a-select v-model:value="d.params.operator" @change="update()">
          <a-select-option value="==">等于 (==)</a-select-option>
          <a-select-option value="!=">不等于 (!=)</a-select-option>
          <a-select-option value=">">大于 (&gt;)</a-select-option>
          <a-select-option value=">=">大于等于 (&gt;=)</a-select-option>
          <a-select-option value="<">小于 (&lt;)</a-select-option>
          <a-select-option value="<=">小于等于 (&lt;=)</a-select-option>
          <a-select-option value="contains">包含</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="期望值">
        <a-auto-complete v-model:value="d.params.value"
          :options="ctx.contextFields.value.map((f:any) => ({ value: '{{' + f.name + '}}', label: f.name }))"
          placeholder="字面量或 {{context变量}}" allow-clear @change="update()" />
      </a-form-item>
    </template>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
function update() { ctx.emitUpdate() }
</script>

<style scoped>
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
.ctx-dot.certain { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
</style>
