<script setup lang = "ts">
  defineProps<{
    titulo: string
    descricao?: string
  }>()
</script>

<template>
  <section class="panel">
    <header class="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6" >
      <div>
        <h2 class="text-lg font-semibold tracking-tight">{{ titulo }}</h2>
        <p v-if="descricao" class="mt-1 text-sm text-muted">
          {{ descricao }}
        </p>
      </div>

      <slot name="acoes"/>
    </header>

    <slot/>
  </section>
</template>