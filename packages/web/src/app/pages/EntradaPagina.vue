<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAutenticacao } from '../hooks/useAuthentication'
import type { InformacoesNo } from '../../domains/auth/types'
import { autenticacaoService } from '../../domains/auth/auth.service'


const router = useRouter()
const route = useRoute()

const {
  usuario,
  primeiroAcesso,
  atualizarSessao,
  entrar,
} = useAutenticacao()

const informacoesNo = ref<InformacoesNo | null>(null)

const nome = ref('')
const login = ref('')
const senha = ref('')
const confirmacaoSenha = ref('')

const mostrarSenha = ref(false)
const carregando = ref(true)
const enviando = ref(false)
const erro = ref('')

const titulo = computed(() =>
  primeiroAcesso.value ? 'Crie a primeira conta' : 'Entre na sua unidade',
)

const descricao = computed(() =>
  primeiroAcesso.value
    ? 'Cadastre a conta de gestão estadual para iniciar o acesso da equipe.'
    : 'Use o login e a senha cadastrados para acessar as informações da sua unidade.',
)

const aviso = computed(() => {
  if (route.query.motivo === 'conexao') {
    return 'Não foi possível verificar a sessão. Tente entrar novamente.'
  }

  if (route.query.motivo === 'sessao') {
    return 'Entre novamente para continuar.'
  }

  return ''
})

async function carregarAcesso() {
  carregando.value = true
  erro.value = ''
  informacoesNo.value = null

  try {
    const [, dadosNo] = await Promise.all([
      atualizarSessao(),
      autenticacaoService.consultarNo(),
    ])

    informacoesNo.value = dadosNo

    if (usuario.value) {
      await router.replace('/painel')
    }
  } catch (falha) {
    erro.value = falha instanceof Error
      ? falha.message
      : 'Não foi possível carregar as informações de acesso.'
  } finally {
    carregando.value = false
  }
}

async function enviarFormulario() {
  if (enviando.value || carregando.value || !informacoesNo.value) {
    return
  }

  erro.value = ''

  if (!login.value.trim() || !senha.value) {
    erro.value = 'Informe o login e a senha.'
    return
  }

  if (primeiroAcesso.value && !nome.value.trim()) {
    erro.value = 'Informe seu nome.'
    return
  }

  if (
    primeiroAcesso.value &&
    senha.value !== confirmacaoSenha.value
  ) {
    erro.value = 'As senhas não coincidem. Confira os dois campos.'
    return
  }

  enviando.value = true

  try {
    if (primeiroAcesso.value) {
      await autenticacaoService.cadastrarPrimeiraConta({
        login: login.value.trim(),
        nome: nome.value.trim(),
        senha: senha.value,
        unidade: informacoesNo.value.id,
      })

      await atualizarSessao()
    }

    await entrar({
      login: login.value.trim(),
      senha: senha.value,
    })

    await router.replace('/painel')
  } catch (falha) {
    erro.value = falha instanceof Error
      ? falha.message
      : 'Não foi possível entrar. Tente novamente.'
  } finally {
    senha.value = ''
    confirmacaoSenha.value = ''
    mostrarSenha.value = false
    enviando.value = false
  }
}

onMounted(carregarAcesso)
</script>

<template>
  <main class="grid min-h-screen bg-canvas lg:grid-cols-2">
    <section
      aria-labelledby="titulo-apresentacao"
      class="relative flex flex-col overflow-hidden
             bg-forest px-8 py-10 text-white sm:px-12 lg:p-16"
    >
      <div
        aria-hidden="true"
        class="pointer-events-none absolute -right-40 -bottom-40
               size-144 rounded-full border border-white/10"
      ></div>

      <div
        aria-hidden="true"
        class="pointer-events-none absolute -right-16 -bottom-16
               size-96 rounded-full border border-white/10"
      ></div>

      <div class="relative flex items-center gap-3">
        <span
          aria-hidden="true"
          class="flex size-11 items-end justify-center
                 gap-1 rounded-xl bg-white/10 p-3"
        >
          <span class="h-3 w-1 rounded-full bg-white"></span>
          <span class="h-5 w-1 rounded-full bg-white"></span>
          <span class="h-4 w-1 rounded-full bg-white"></span>
        </span>

        <div>
          <p class="text-xl font-bold tracking-tight">SoroAM</p>
          <p class="text-xs text-emerald-100">Rede de distribuição</p>
        </div>
      </div>

      <div class="relative my-12 max-w-lg lg:my-auto lg:py-24">
        <h1
          id="titulo-apresentacao"
          class="text-4xl leading-tight font-semibold
                 tracking-tight sm:text-5xl lg:text-6xl"
        >
          Uma rede<br />
          para cuidar.
        </h1>

        <p class="mt-6 max-w-md leading-8 text-emerald-50/85">
          Estoques, atendimentos e distribuição de soros em uma visão
          compartilhada entre as unidades.
        </p>
      </div>

      <p class="relative text-sm text-emerald-100">
        Equipe de saúde e gestão estadual
      </p>
    </section>

    <section
      aria-labelledby="titulo-login"
      class="flex items-center justify-center px-6 py-12 sm:px-12"
    >
      <div class="w-full max-w-md">
        <p class="text-sm font-medium text-river">Acesso da equipe</p>

        <h2
          id="titulo-login"
          class="mt-3 text-3xl font-semibold tracking-tight text-ink"
        >
          {{ titulo }}
        </h2>

        <p class="mt-4 text-sm leading-7 text-muted">
          {{ descricao }}
        </p>

        <div
          v-if="informacoesNo"
          class="mt-6 rounded-lg border border-line bg-white px-4 py-3"
        >
          <p class="text-xs text-muted">Unidade de acesso</p>
          <p class="mt-1 text-sm font-semibold text-forest">
            {{ informacoesNo.nome }}
          </p>
        </div>

        <p
          v-if="carregando"
          role="status"
          class="mt-8 text-sm text-muted"
        >
          Verificando acesso…
        </p>

        <p
          v-if="aviso && !erro && !carregando"
          role="status"
          class="mt-6 rounded-lg bg-mist px-4 py-3 text-sm text-forest"
        >
          {{ aviso }}
        </p>

        <Transition>
          <p
            v-if="erro"
            id="erro-login"
            role="alert"
            class="mt-6 rounded-lg border border-red-200
                  bg-red-50 px-4 py-3 text-sm leading-6 text-red-800"
          >
            {{ erro }}
          </p>
        </Transition>

        <button
          v-if="!carregando && !informacoesNo"
          type="button"
          class="button-secondary mt-5"
          @click="carregarAcesso"
        >
          Tentar novamente
        </button>

        <form
          v-if="!carregando && informacoesNo"
          class="mt-7 space-y-5"
          :aria-busy="enviando"
          :aria-describedby="erro ? 'erro-login' : undefined"
          @submit.prevent="enviarFormulario"
        >
          <fieldset :disabled="enviando" class="space-y-5">
            <legend class="sr-only">
              {{ primeiroAcesso ? 'Cadastro inicial' : 'Credenciais de acesso' }}
            </legend>

            <div v-if="primeiroAcesso">
              <label for="nome" class="field-label">Nome completo</label>

              <input
                id="nome"
                v-model="nome"
                name="nome"
                type="text"
                autocomplete="name"
                required
                class="field"
                placeholder="Seu nome"
              />
            </div>

            <div>
              <label for="login" class="field-label">Usuário</label>

              <input
                id="login"
                v-model="login"
                name="login"
                type="text"
                autocomplete="username"
                autocapitalize="none"
                :spellcheck="false"
                required
                class="field"
                placeholder="Seu usuário"
              />
            </div>

            <div>
              <label for="senha" class="field-label">Senha</label>

              <div class="relative">
                <input
                  id="senha"
                  v-model="senha"
                  name="senha"
                  :type="mostrarSenha ? 'text' : 'password'"
                  :autocomplete="primeiroAcesso ? 'new-password' : 'current-password'"
                  :minlength="primeiroAcesso ? 8 : undefined"
                  :aria-describedby="primeiroAcesso ? 'ajuda-senha' : undefined"
                  required
                  class="field pr-24"
                  placeholder="Digite sua senha"
                />

                <button
                  type="button"
                  aria-controls="senha"
                  :aria-pressed="mostrarSenha"
                  class="absolute inset-y-0 right-1 my-1
                         rounded px-3 text-xs font-semibold text-river"
                  @click="mostrarSenha = !mostrarSenha"
                >
                  {{ mostrarSenha ? 'Ocultar' : 'Mostrar' }}
                </button>
              </div>

              <p
                v-if="primeiroAcesso"
                id="ajuda-senha"
                class="mt-2 text-xs text-muted"
              >
                Use pelo menos 8 caracteres.
              </p>
            </div>

            <div v-if="primeiroAcesso">
              <label for="confirmacao-senha" class="field-label">
                Confirme a senha
              </label>

              <input
                id="confirmacao-senha"
                v-model="confirmacaoSenha"
                name="confirmacao-senha"
                :type="mostrarSenha ? 'text' : 'password'"
                autocomplete="new-password"
                minlength="8"
                required
                class="field"
                placeholder="Digite a senha novamente"
              />
            </div>

            <button
              type="submit"
              class="button-primary min-h-12 w-full
                     disabled:cursor-not-allowed disabled:opacity-60"
            >
              {{
                enviando
                  ? 'Aguarde…'
                  : primeiroAcesso
                    ? 'Criar conta e entrar'
                    : 'Entrar'
              }}
            </button>
          </fieldset>
        </form>

        <p class="mt-6 text-xs leading-6 text-muted">
          Acesse pelo endereço da sua unidade. Se ainda não possui uma
          conta, procure a coordenação responsável.
        </p>
      </div>
    </section>
  </main>
</template>