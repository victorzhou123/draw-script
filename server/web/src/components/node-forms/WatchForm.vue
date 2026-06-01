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
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData

const fieldOptions = computed(() =>
  ctx.contextFields.value.map(f => ({ label: f.name, value: f.name }))
)

function update() { ctx.emitUpdate() }
</script>
