<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const itens = [
  {
    nome: 'Visão geral',
    rota: '/painel',
  },
]
</script>

<template>
  <aside
    class="sidebar border-b border-white/10 bg-forest p-5 text-white
           lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-64
           lg:flex-col lg:overflow-y-auto lg:border-r
           lg:border-b-0 lg:p-6"
  >
    <RouterLink
      to="/painel"
      class="flex items-center gap-3 rounded-lg"
      aria-label="AMpolo — visão geral"
    >
      <span
        aria-hidden="true"
        class="flex size-11 shrink-0 items-end justify-center
               gap-1 rounded-xl border border-white/15 bg-white/10 p-3"
      >
        <span class="h-3 w-1 rounded-full bg-white"></span>
        <span class="h-5 w-1 rounded-full bg-white"></span>
        <span class="h-4 w-1 rounded-full bg-white"></span>
      </span>

      <span>
        <span class="block text-xl font-bold tracking-tight text-white">
          AMpolo
        </span>

        <span class="mt-0.5 block text-xs text-emerald-100">
          Rede de distribuição
        </span>
      </span>
    </RouterLink>

    <nav aria-label="Navegação principal" class="mt-7 lg:mt-11">
      <p class="mb-3 px-3 text-xs font-medium text-emerald-100">
        Área da equipe
      </p>

      <div class="flex gap-2 overflow-x-auto py-1 lg:flex-col">
        <RouterLink
          v-for="item in itens"
          :key="item.rota"
          :to="item.rota"
          class="nav-item flex min-h-12 shrink-0 items-center
                 gap-3 rounded-lg px-3 py-3 text-sm font-medium"
          :class="
            route.path === item.rota
              ? 'bg-mist text-forest hover:bg-white'
              : 'text-emerald-50 hover:bg-white/10 hover:text-white'
          "
        >
          <svg
            aria-hidden="true"
            width="19"
            height="19"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
          >
            <rect x="3" y="3" width="7" height="7" rx="1.5" />
            <rect x="14" y="3" width="7" height="7" rx="1.5" />
            <rect x="3" y="14" width="7" height="7" rx="1.5" />
            <rect x="14" y="14" width="7" height="7" rx="1.5" />
          </svg>

          {{ item.nome }}

          <span
            v-if="route.path === item.rota"
            aria-hidden="true"
            class="ml-auto size-1.5 rounded-full bg-river"
          ></span>
        </RouterLink>
      </div>
    </nav>

    <div class="mt-auto hidden pt-8 lg:block">
      <div class="border-t border-white/15 pt-5">
        <p class="text-sm font-semibold text-white">
          Logística de soros
        </p>

        <p class="mt-2 text-xs leading-6 text-emerald-100">
          Acompanhamento de estoques e distribuição
          entre unidades de saúde.
        </p>
      </div>
    </div>
  </aside>
</template>