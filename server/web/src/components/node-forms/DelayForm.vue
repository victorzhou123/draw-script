<template>
  <div>
    <a-form-item label="秒数">
      <a-input-number v-model:value="d.params.seconds" :min="0" :step="0.1" @change="update()" />
    </a-form-item>
    <a-form-item label="毫秒 (额外)">
      <a-input-number v-model:value="d.params.ms" :min="0" :step="100" @change="update()" />
    </a-form-item>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
function update() { ctx.emitUpdate() }
</script>
