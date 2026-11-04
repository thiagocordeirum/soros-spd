<script setup lang ="ts">
import { RouterLink } from 'vue-router';

const itens = [
  {nome: 'Visão Geral', rota: '/painel'}
]
</script>

<template>
  <aside
    class="border-b border-line bg-white p-5
           lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-64
           lg:flex-col lg:border-r lg:border-b-0 lg:p-6"
  >
    <RouterLink to="/painel" class="flex items-center gap-3 rounded-lg">
      <span
        aria-hidden="true"
        class="flex size-11 items-end justify-center gap-1 rounded-xl bg-river p-3"
      >
        <span class="h-3 w-1 rounded-full bg-white"></span>
        <span class="h-5 w-1 rounded-full bg-white"></span>
        <span class="h-4 w-1 rounded-full bg-white"></span>
      </span>

      <span>
        <span class="block text-xl font-bold tracking-tight text-forest">
          AMpolo
        </span>
        <span class="text-xs text-muted">Rede de distribuição</span>
      </span>
    </RouterLink>

    <nav aria-label="Navegação principal" class="mt-7 lg:mt-10">
      <p class="mb-3 hidden px-3 text-xs font-medium text-muted lg:block">
        Área da equipe
      </p>

      <div class="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible">
        <RouterLink
          v-for="item in itens"
          :key="item.rota"
          :to="item.rota"
          class="nav-item rounded-lg px-3 py-3 text-sm font-medium
                 whitespace-nowrap text-muted hover:bg-mist hover:text-forest"
          exact-active-class="bg-mist text-forest!"
        >
          {{ item.nome }}
        </RouterLink>
      </div>
    </nav>

    <div class="mt-auto hidden border-t border-line pt-5 lg:block">
      <p class="text-sm font-semibold text-forest">Protótipo da equipe</p>
      <p class="mt-1 text-xs leading-5 text-muted">
        Navegação local com dados demonstrativos.
      </p>

      <RouterLink to="/entrada" class="mt-4 inline-block text-xs text-river underline">
        Voltar à entrada
      </RouterLink>
    </div>
  </aside>
</template>