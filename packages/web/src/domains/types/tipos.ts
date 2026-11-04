export type SituacaoEstoque = 'Regular' | 'Atenção' | 'Crítico'

export type TomBadge = 'verde' | 'amarelo' | 'vermelho' | 'cinza'

export interface Unidade {
  id: string
  nome: string
  nivel: string
  municipio: string
  ampolas: number
  percentualAlvo: number
  situacao: SituacaoEstoque
  atualizadoHa: string
}

export interface Lote {
  id: string
  soro: string
  unidade: string
  validade: string
  quantidade: number
  situacao: 'Disponível' | 'Próximo do vencimento' | 'Vencido'
}

export interface Atendimento {
  id: string
  data: string
  unidade: string
  agravo: string
  gravidade: string
  soro: string
  ampolas: number
}

export interface Remessa {
  id: string
  origem: string
  destino: string
  soro: string
  quantidade: number
  situacao: 'Em transporte' | 'Aguardando recebimento' | 'Recebida'
}

export interface Pedido {
  id: string
  unidade: string
  fornecedor: string
  soro: string
  quantidade: number
  situacao: 'Aberto' | 'Atendido'
}

export interface Alerta {
  id: string
  titulo: string
  descricao: string
  unidade: string
  prioridade: 'Atenção' | 'Crítico'
  atualizadoHa: string
}

export interface Usuario {
  login: string
  nome: string
  perfil: string
  unidade: string
  ativo: boolean
}

export interface Vizinho {
  id: string
  nome: string
  endereco: string
  situacao: 'Conectado' | 'Sem contato'
  ultimaTroca: string
}

export interface UsoDiario {
  dia: string
  ampolas: number
}