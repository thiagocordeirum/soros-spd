import { computed, onScopeDispose, ref, shallowRef } from 'vue'
import { ErroHttp } from '../../service/cliente'
import type { DadosPainel, UnidadePainelApi } from '../../domains/painel/types'
import { painelService } from '../../service/painel'

export function usePainel() {
  const dados = shallowRef<DadosPainel | null>(null)

  const carregando = ref(false)
  const erro = ref('')
  const statusErro = ref<number | null>(null)
  const consultadoEm = ref<Date | null>(null)

  const busca = ref('')
  const filtro = ref<'todas' | 'sem-contato'>('todas')

  let descartado = false

  onScopeDispose(() => {
    descartado = true
  })

  const dadosDisponiveis = computed(() => dados.value !== null)

  const unidades = computed(() =>
    dados.value?.painel.unidades ?? [],
  )

  const unidadesConhecidas = computed(() =>
    unidades.value.filter(
      (unidade) => unidade.atualizado_ha_s !== null,
    ),
  )

  const unidadesSemContato = computed(() =>
    unidades.value.filter(
      (unidade) => unidade.atualizado_ha_s === null,
    ),
  )

  function normalizar(valor: string) {
    return valor
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim()
  }

  const unidadesFiltradas = computed(() =>
    unidades.value.filter((unidade) => {
      const correspondeBusca = normalizar(
        `${unidade.nome} ${unidade.regiao ?? ''}`,
      ).includes(normalizar(busca.value))

      const correspondeFiltro =
        filtro.value === 'todas' ||
        unidade.atualizado_ha_s === null

      return correspondeBusca && correspondeFiltro
    }),
  )

  function estoqueDisponivel(unidade: UnidadePainelApi) {
    return unidade.soros.reduce(
      (total, soro) => total + soro.estoque,
      0,
    )
  }

  const totalAmpolas = computed(() =>
    unidadesConhecidas.value.reduce(
      (total, unidade) => total + estoqueDisponivel(unidade),
      0,
    ),
  )

  const ampolasEmTransito = computed(() =>
    unidades.value.reduce(
      (total, unidade) => total + unidade.a_caminho,
      0,
    ),
  )

  const vencimentos = computed(() =>
    dados.value?.painel.vencendo ?? [],
  )

  const alertas = computed(() =>
    dados.value?.painel.alertas ?? [],
  )

  const remessasPendentes = computed(() => {
    if (!dados.value) return []

    const remessas = [
      ...dados.value.remessas.chegando,
      ...dados.value.remessas.enviadas,
    ]

    return [...new Map(
      remessas.map((remessa) => [remessa.id, remessa]),
    ).values()]
  })

  const usoDiario = computed(() => {
    const graficos = dados.value?.graficos

    if (!graficos) return []

    return graficos.dias.map((data, indice) => ({
      data,
      ampolas: Object.values(graficos.uso_diario).reduce(
        (total, serie) => total + (serie[indice] ?? 0),
        0,
      ),
    }))
  })

  const maiorUso = computed(() =>
    Math.max(1, ...usoDiario.value.map((item) => item.ampolas)),
  )

  const totalUso = computed(() =>
    usoDiario.value.reduce(
      (total, item) => total + item.ampolas,
      0,
    ),
  )

  function nomeUnidade(id: string) {
    return dados.value?.info.unidades[id]?.nome ?? id
  }

  function nomeSoro(id: string) {
    return dados.value?.info.soros[id] ?? id
  }

  function ocupacaoReservada(unidade: UnidadePainelApi) {
    if (
      unidade.atualizado_ha_s === null ||
      unidade.capacidade <= 0
    ) {
      return '—'
    }

    const percentual =
      ((unidade.total + unidade.a_caminho) / unidade.capacidade) * 100

    return `${percentual.toLocaleString('pt-BR', {
      maximumFractionDigits: 1,
    })}%`
  }

  function formatarIdade(segundos: number | null) {
    if (segundos === null) return 'Sem contato'
    if (segundos < 60) return 'Menos de 1 min'
    if (segundos < 3600) return `${Math.floor(segundos / 60)} min`
    if (segundos < 86400) return `${Math.floor(segundos / 3600)} h`

    return `${Math.floor(segundos / 86400)} dias`
  }

  function formatarData(data: string) {
    return data.split('-').reverse().join('/')
  }

  function limparFiltros() {
    busca.value = ''
    filtro.value = 'todas'
  }

  async function carregar() {
    if (carregando.value || descartado) return

    carregando.value = true
    erro.value = ''
    statusErro.value = null
    dados.value = null
    consultadoEm.value = null

    try {
      const resposta = await painelService.carregar()

      if (descartado) return

      dados.value = resposta
      consultadoEm.value = new Date()
    } catch (falha) {
      if (descartado) return

      statusErro.value = falha instanceof ErroHttp
        ? falha.status
        : null

      erro.value = falha instanceof Error
        ? falha.message
        : 'Não foi possível carregar o painel.'
    } finally {
      if (!descartado) {
        carregando.value = false
      }
    }
  }

  return {
    dadosDisponiveis,
    carregando,
    erro,
    statusErro,
    consultadoEm,
    busca,
    filtro,
    unidades,
    unidadesConhecidas,
    unidadesSemContato,
    unidadesFiltradas,
    totalAmpolas,
    ampolasEmTransito,
    vencimentos,
    alertas,
    remessasPendentes,
    usoDiario,
    maiorUso,
    totalUso,
    estoqueDisponivel,
    ocupacaoReservada,
    nomeUnidade,
    nomeSoro,
    formatarIdade,
    formatarData,
    limparFiltros,
    carregar,
  }
}