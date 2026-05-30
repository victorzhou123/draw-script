<template>
  <a-form-item label="Webhook 名称">
    <a-input v-model:value="d.params.name" @change="update()" />
  </a-form-item>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FORM_CTX } from './useFormContext'

const ctx = inject(FORM_CTX)!
const d = ctx.localData
function update() { ctx.emitUpdate() }
</script>
