<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAutenticacao } from '../hooks/useAuthentication'

const router = useRouter()
const { usuario, sair } = useAutenticacao()

const saindo = ref(false)
const erro = ref('')

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
      : 'Não foi possível encerrar a sessão.'
  } finally {
    saindo.value = false
  }
}
</script>

<template>
  <main class="min-h-screen bg-canvas px-6 py-10 text-ink">
    <section class="mx-auto max-w-3xl overflow-hidden rounded-2xl border border-line bg-white">
      <header class="bg-forest p-8 text-white">
        <p class="text-sm text-emerald-100">AMpolo · Área da equipe</p>

        <h1 class="mt-3 text-3xl font-semibold tracking-tight">
          Olá, {{ usuario?.nome }}.
        </h1>

        <p class="mt-3 text-sm text-emerald-50/85">
          Sua sessão foi iniciada.
        </p>
      </header>

      <div class="p-8">
        <dl class="grid gap-6 sm:grid-cols-2">
          <div>
            <dt class="text-xs text-muted">Unidade</dt>
            <dd class="mt-2 font-semibold">{{ usuario?.unidade_nome }}</dd>
          </div>

          <div>
            <dt class="text-xs text-muted">Perfil de acesso</dt>
            <dd class="mt-2 font-semibold">{{ usuario?.tipo_nome }}</dd>
          </div>

          <div>
            <dt class="text-xs text-muted">Login</dt>
            <dd class="mt-2">{{ usuario?.login }}</dd>
          </div>
        </dl>

        <p
          v-if="erro"
          role="alert"
          class="mt-6 rounded-lg bg-red-50 p-4 text-sm text-red-800"
        >
          {{ erro }}
        </p>

        <button
          type="button"
          :disabled="saindo"
          class="button-secondary mt-8
                 disabled:cursor-not-allowed disabled:opacity-60"
          @click="encerrarSessao"
        >
          {{ saindo ? 'Saindo…' : 'Sair da conta' }}
        </button>
      </div>
    </section>
  </main>
</template>