export interface SoroPainelApi {
  soro: string
  estoque: number
  uso_mes: number
  dura_meses: number | null
}

export interface UnidadePainelApi {
  unidade: string
  nome: string
  nivel: 'estado' | 'polo' | 'posto'
  regiao: string | null
  total: number
  capacidade: number
  a_caminho: number
  atualizado_ha_s: number | null
  soros: SoroPainelApi[]
}

export interface VencimentoApi {
  unidade: string
  nome: string
  lote: string
  soro: string
  validade: string
  qtd: number
  vence_em_dias: number
}

export interface AlertaSurtoApi {
  id: string
  regiao: string
  dia: string
  observado: number
  media: number
  limiar: number
  por: string
}

export interface PainelApi {
  unidades: UnidadePainelApi[]
  vencendo: VencimentoApi[]
  alertas: AlertaSurtoApi[]
}

export interface GraficosApi {
  dias: string[]
  uso_diario: Record<string, number[]>
}

export interface RemessaApi {
  id: string
  origem: string
  destino: string
  soro: string
  qtd: number
  data: string
}

export interface RemessasApi {
  chegando: RemessaApi[]
  enviadas: RemessaApi[]
}

export interface InformacoesPainelApi {
  id: string
  nome: string
  estado: string
  hoje: string
  soros: Record<string, string>
  unidades: Record<
    string,
    {
      nome: string
      nivel: string
      url: string
    }
  >
}

export interface DadosPainel {
  info: InformacoesPainelApi
  painel: PainelApi
  graficos: GraficosApi
  remessas: RemessasApi
}