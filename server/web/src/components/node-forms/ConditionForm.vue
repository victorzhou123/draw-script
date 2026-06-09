<template>
  <div>
    <a-form-item label="逻辑运算符">
      <a-radio-group v-model:value="d.operator" button-style="solid" @change="update()">
        <a-radio-button value="and">AND（全部满足）</a-radio-button>
        <a-radio-button value="or">OR（任一满足）</a-radio-button>
      </a-radio-group>
    </a-form-item>

    <div v-for="(cond, idx) in d.conditions" :key="idx" class="cond-item">
      <div class="cond-header">
        <span class="cond-label">条件 {{ idx + 1 }}</span>
        <a-button type="text" danger size="small" @click="removeCond(idx)">删除</a-button>
      </div>

      <a-form-item label="判断类型">
        <a-select v-model:value="cond.condition_type" @change="onTypeChange(cond)">
          <a-select-option value="variable_compare">变量比较</a-select-option>
          <a-select-option value="boolean_check">布尔值判断</a-select-option>
        </a-select>
      </a-form-item>

      <template v-if="cond.condition_type === 'boolean_check'">
        <a-form-item label="变量路径">
          <a-auto-complete
            v-model:value="cond.params.variable"
            :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))"
            placeholder="例如: last_vision_result.found"
            allow-clear
            @change="update()"
          >
            <template #option="{ value: val }">
              <span class="ctx-dot" :class="ctx.contextFields.value.find((f:any) => f.name === val)?.certain ? 'certain' : 'conditional'" />
              {{ val }}
            </template>
          </a-auto-complete>
          <div class="hint-text">判断该变量的值是否为真（非空、非零、非False）</div>
        </a-form-item>
      </template>

      <template v-if="cond.condition_type === 'variable_compare'">
        <a-form-item label="变量路径">
          <a-auto-complete
            v-model:value="cond.params.variable"
            :options="ctx.contextFields.value.map((f:any) => ({ value: f.name }))"
            placeholder="例如: last_http_response.status_code"
            allow-clear
            @change="update()"
          >
            <template #option="{ value: val }">
              <span class="ctx-dot" :class="ctx.contextFields.value.find((f:any) => f.name === val)?.certain ? 'certain' : 'conditional'" />
              {{ val }}
            </template>
          </a-auto-complete>
          <div v-if="!ctx.contextFields.value.length" class="hint-text">当前节点上游暂无 context 变量</div>
        </a-form-item>
        <a-form-item label="运算符">
          <a-select v-model:value="cond.params.operator" @change="update()">
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
          <a-auto-complete
            v-model:value="cond.params.value"
            :options="ctx.contextFields.value.map((f:any) => ({ value: '{{' + f.name + '}}', label: f.name }))"
            placeholder='500 / 3.14 / "text" / {{变量}}'
            allow-clear
            @change="update()"
          />
        </a-form-item>
      </template>

      <a-divider v-if="idx < d.conditions.length - 1" style="margin: 8px 0 4px">
        <span class="op-badge">{{ d.operator === 'and' ? 'AND' : 'OR' }}</span>
      </a-divider>
    </div>

    <div v-if="!d.conditions?.length" class="hint-text" style="margin: 4px 0 8px">请添加至少一个条件</div>
    <a-button type="dashed" block @click="addCond()">+ 添加条件</a-button>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

function update() { ctx.emitUpdate() }

function addCond() {
  if (!Array.isArray(d.value.conditions)) d.value.conditions = []
  d.value.conditions.push({ condition_type: 'variable_compare', params: { operator: '==' } })
  update()
}

function removeCond(idx: number) {
  d.value.conditions.splice(idx, 1)
  update()
}

function onTypeChange(cond: any) {
  cond.params = cond.condition_type === 'variable_compare' ? { operator: '==' } : {}
  update()
}
</script>

<style scoped>
.hint-text { font-size: 11px; color: #444; margin-bottom: 8px; }
.ctx-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
.ctx-dot.certain { background: #52c41a; }
.ctx-dot.conditional { background: #faad14; }
.cond-item { border: 1px solid #333; border-radius: 6px; padding: 8px 12px 2px; margin-bottom: 8px; }
.cond-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.cond-label { font-size: 12px; color: #888; font-weight: 600; }
.op-badge { font-size: 11px; color: #faad14; background: #2b2111; padding: 1px 8px; border-radius: 3px; border: 1px solid #3f2e00; }
</style>
