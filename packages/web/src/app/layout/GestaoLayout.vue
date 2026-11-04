<script setup lang="ts">
import { RouterView } from 'vue-router'

import AppHeader from '../components/AppHeader.vue'
import AppSidebar from '../components/AppSidebar.vue'
</script>

<template>
  <div class="min-h-screen bg-canvas text-ink">
    <a href="#conteudo" class="skip-link">
      Pular para o conteúdo
    </a>

    <AppSidebar />

    <div class="lg:ml-64">
      <AppHeader />

      <main
        id="conteudo"
        tabindex="-1"
        class="mx-auto max-w-400 p-5 sm:p-8 lg:p-10"
      >
        <RouterView v-slot="{ Component, route }">
          <Transition name="page" mode="out-in">
            <div :key="route.path">
              <component :is="Component" />
            </div>
          </Transition>
        </RouterView>
      </main>

      <footer
        class="flex flex-wrap justify-between gap-2
               px-5 pb-6 text-xs text-muted sm:px-8 lg:px-10"
      >
        <p>AMpolo · Logística de soros antivenenos</p>
        <p>Informações conforme a última consulta ao nó</p>
      </footer>
    </div>
  </div>
</template>