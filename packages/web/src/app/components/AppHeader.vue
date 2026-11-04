<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAutenticacao } from '../hooks/useAuthentication'

const route = useRoute()
const router = useRouter()

const { usuario, sair } = useAutenticacao()

const saindo = ref(false)
const erro = ref('')

const titulo = computed(() =>
  String(route.meta.titulo ?? 'Área da equipe'),
)

const iniciais = computed(() => {
  const partes = usuario.value?.nome
    .trim()
    .split(/\s+/)
    .filter(Boolean) ?? []

  const primeira = partes[0]?.charAt(0) ?? ''
  const ultima = partes.length > 1
    ? partes[partes.length - 1]?.charAt(0) ?? ''
    : ''

  return `${primeira}${ultima}`.toUpperCase() || 'AM'
})

async function encerrarSessao() {
  if (saindo.value) return

  saindo.value = true
  erro.value = ''

  try {
    await sair()
    await router.replace('/entrada')
  } catch (falha) {
    erro.value = falha instanceof Error
      ? falha.message
      : 'Não foi possível sair. Tente novamente.'
  } finally {
    saindo.value = false
  }
}
</script>

<template>
  <header class="border-b border-line bg-white">
    <div
      class="flex flex-wrap items-center justify-between
             gap-5 px-5 py-5 sm:px-8 lg:px-10"
    >
      <div>
        <p class="text-xs text-muted">
          {{ usuario?.unidade_nome }}
        </p>

        <p class="mt-1 text-lg font-semibold tracking-tight">
          {{ titulo }}
        </p>
      </div>

      <div class="flex items-center gap-3 sm:gap-5">
        <span
          aria-hidden="true"
          class="grid size-10 shrink-0 place-items-center
                 rounded-full bg-mist text-sm font-semibold text-river"
        >
          {{ iniciais }}
        </span>

        <div class="min-w-0">
          <p class="max-w-48 truncate text-sm font-semibold">
            {{ usuario?.nome }}
          </p>

          <p class="mt-0.5 text-xs text-muted">
            {{ usuario?.tipo_nome }}
          </p>
        </div>

        <button
          type="button"
          class="button-secondary disabled:opacity-60"
          :disabled="saindo"
          @click="encerrarSessao"
        >
          {{ saindo ? 'Saindo…' : 'Sair' }}
        </button>
      </div>
    </div>

    <Transition name="feedback">
      <p
        v-if="erro"
        role="alert"
        class="border-t border-red-100 bg-red-50
               px-5 py-3 text-sm text-red-800 sm:px-8 lg:px-10"
      >
        {{ erro }}
      </p>
    </Transition>
  </header>
</template>