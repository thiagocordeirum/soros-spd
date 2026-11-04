<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const titulo = computed(() => String(route.meta.titulo ?? 'Gestão da rede'))
</script>

<template>
  <header
    class="flex flex-wrap items-center justify-between gap-4
           border-b border-line bg-white px-5 py-5 sm:px-8 lg:px-10"
  >
    <div>
      <p class="text-xs text-muted">Rede estadual / Amazonas</p>
      <p class="mt-1 text-lg font-semibold tracking-tight">{{ titulo }}</p>
    </div>

    <div class="flex items-center gap-3">
      <span class="hidden text-xs text-muted sm:block">Dados de exemplo</span>

      <span
        aria-hidden="true"
        class="grid size-10 place-items-center rounded-full
               bg-mist text-sm font-semibold text-river"
      >
        GE
      </span>

      <div>
        <p class="text-sm font-semibold">Gestão estadual</p>
        <RouterLink to="/entrada" class="text-xs text-river underline">
          Voltar à entrada
        </RouterLink>
      </div>
    </div>
  </header>
</template>