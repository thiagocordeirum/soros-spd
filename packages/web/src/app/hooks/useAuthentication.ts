import { computed, readonly, shallowRef } from 'vue'
import type { Credenciais, Permissao, SessaoResposta } from '../../domains/auth/types'
import { autenticacaoService } from '../../domains/auth/auth.service'



const sessao = shallowRef<SessaoResposta | null>(null)

const usuario = computed(() => sessao.value?.usuario ?? null)

const autenticado = computed(() => usuario.value !== null)

const primeiroAcesso = computed(
  () => sessao.value?.primeiro_acesso ?? false,
)

const permissoes = computed(() => sessao.value?.pode ?? [])

async function atualizarSessao() {
  try {
    const resposta = await autenticacaoService.consultarSessao()
    sessao.value = resposta

    return resposta
  } catch (erro) {
    sessao.value = null
    throw erro
  }
}

async function entrar(credenciais: Credenciais) {
  sessao.value = null

  await autenticacaoService.entrar(credenciais)

  const resposta = await atualizarSessao()

  if (!resposta.usuario) {
    throw new Error(
      'O servidor não confirmou a sessão. Verifique se os cookies estão habilitados.',
    )
  }

  return resposta.usuario
}

async function sair() {
  await autenticacaoService.sair()
  sessao.value = null
}

function pode(permissao: Permissao) {
  return permissoes.value.includes(permissao)
}

export function useAutenticacao() {
  return {
    sessao: readonly(sessao),
    usuario,
    autenticado,
    primeiroAcesso,
    permissoes,
    atualizarSessao,
    entrar,
    sair,
    pode,
  }
}