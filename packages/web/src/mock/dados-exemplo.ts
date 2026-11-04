import type { 
  Alerta, 
  Atendimento, 
  Lote, 
  Pedido, 
  Remessa, 
  Unidade, 
  UsoDiario, 
  Usuario, 
  Vizinho 
} from "../domains/types/tipos"


export const unidadesExemplo: Unidade[] = [
  {
    id: 'tabatinga',
    nome: 'Polo Tabatinga',
    nivel: 'Polo regional',
    municipio: 'Tabatinga',
    ampolas: 420,
    percentualAlvo: 84,
    situacao: 'Regular',
    atualizadoHa: '2 min',
  },
  {
    id: 'tefe',
    nome: 'Polo Tefé',
    nivel: 'Polo regional',
    municipio: 'Tefé',
    ampolas: 356,
    percentualAlvo: 71,
    situacao: 'Regular',
    atualizadoHa: '5 min',
  },
  {
    id: 'atalaia',
    nome: 'Atalaia do Norte',
    nivel: 'Ponto de soro',
    municipio: 'Atalaia do Norte',
    ampolas: 64,
    percentualAlvo: 21,
    situacao: 'Crítico',
    atualizadoHa: '48 min',
  },
  {
    id: 'benjamin',
    nome: 'Benjamin Constant',
    nivel: 'Ponto de soro',
    municipio: 'Benjamin Constant',
    ampolas: 408,
    percentualAlvo: 46,
    situacao: 'Atenção',
    atualizadoHa: '12 min',
  },
]

export const lotesExemplo: Lote[] = [
  {
    id: 'SAB-2026-117',
    soro: 'Antibotrópico',
    unidade: 'Polo Tabatinga',
    validade: '2027-08-20',
    quantidade: 120,
    situacao: 'Disponível',
  },
  {
    id: 'SABC-2026-042',
    soro: 'Antibotrópico-laquético',
    unidade: 'Polo Tefé',
    validade: '2026-12-10',
    quantidade: 48,
    situacao: 'Próximo do vencimento',
  },
  {
    id: 'SAC-2026-008',
    soro: 'Anticrotálico',
    unidade: 'Atalaia do Norte',
    validade: '2027-06-15',
    quantidade: 16,
    situacao: 'Disponível',
  },
  {
    id: 'SAE-2025-021',
    soro: 'Antiescorpiônico',
    unidade: 'Benjamin Constant',
    validade: '2026-10-01',
    quantidade: 8,
    situacao: 'Vencido',
  },
]

export const atendimentosExemplo: Atendimento[] = [
  {
    id: 'AT-1028',
    data: '2026-11-03',
    unidade: 'Atalaia do Norte',
    agravo: 'Botrópico',
    gravidade: 'Moderado',
    soro: 'Antibotrópico',
    ampolas: 8,
  },
  {
    id: 'AT-1027',
    data: '2026-11-03',
    unidade: 'Polo Tefé',
    agravo: 'Escorpiônico',
    gravidade: 'Leve',
    soro: 'Não utilizado',
    ampolas: 0,
  },
  {
    id: 'AT-1026',
    data: '2026-11-02',
    unidade: 'Benjamin Constant',
    agravo: 'Botrópico',
    gravidade: 'Moderado',
    soro: 'Antibotrópico',
    ampolas: 6,
  },
]

export const remessasExemplo: Remessa[] = [
  {
    id: 'REM-0241',
    origem: 'Polo Tabatinga',
    destino: 'Atalaia do Norte',
    soro: 'Antibotrópico',
    quantidade: 40,
    situacao: 'Em transporte',
  },
  {
    id: 'REM-0240',
    origem: 'Secretaria estadual',
    destino: 'Polo Tefé',
    soro: 'Anticrotálico',
    quantidade: 24,
    situacao: 'Aguardando recebimento',
  },
  {
    id: 'REM-0239',
    origem: 'Polo Tabatinga',
    destino: 'Benjamin Constant',
    soro: 'Antibotrópico-laquético',
    quantidade: 60,
    situacao: 'Recebida',
  },
]

export const pedidosExemplo: Pedido[] = [
  {
    id: 'PED-0083',
    unidade: 'Atalaia do Norte',
    fornecedor: 'Polo Tabatinga',
    soro: 'Antibotrópico',
    quantidade: 40,
    situacao: 'Aberto',
  },
  {
    id: 'PED-0082',
    unidade: 'Polo Tefé',
    fornecedor: 'Secretaria estadual',
    soro: 'Anticrotálico',
    quantidade: 24,
    situacao: 'Atendido',
  },
]

export const alertasExemplo: Alerta[] = [
  {
    id: 'AL-001',
    titulo: 'Estoque abaixo do alvo',
    descricao: 'A unidade apresenta 21% do estoque-alvo no cenário demonstrativo.',
    unidade: 'Atalaia do Norte',
    prioridade: 'Crítico',
    atualizadoHa: '48 min',
  },
  {
    id: 'AL-002',
    titulo: 'Lote próximo do vencimento',
    descricao: 'O lote SABC-2026-042 contém 48 ampolas com validade em 10/12/2026.',
    unidade: 'Polo Tefé',
    prioridade: 'Atenção',
    atualizadoHa: '5 min',
  },
  {
    id: 'AL-003',
    titulo: 'Informações sem atualização recente',
    descricao: 'Confira a idade dos dados antes de planejar uma reposição.',
    unidade: 'Atalaia do Norte',
    prioridade: 'Atenção',
    atualizadoHa: '48 min',
  },
]

export const usuariosExemplo: Usuario[] = [
  {
    login: 'gestor',
    nome: 'Marina Lima',
    perfil: 'Gestão estadual',
    unidade: 'Secretaria estadual',
    ativo: true,
  },
  {
    login: 'coord.tabatinga',
    nome: 'Carlos Souza',
    perfil: 'Coordenação',
    unidade: 'Polo Tabatinga',
    ativo: true,
  },
  {
    login: 'prof.atalaia',
    nome: 'Ana Oliveira',
    perfil: 'Profissional de saúde',
    unidade: 'Atalaia do Norte',
    ativo: true,
  },
  {
    login: 'prof.benjamin',
    nome: 'Paulo Santos',
    perfil: 'Profissional de saúde',
    unidade: 'Benjamin Constant',
    ativo: false,
  },
]

export const vizinhosExemplo: Vizinho[] = [
  {
    id: 'tabatinga',
    nome: 'Polo Tabatinga',
    endereco: '127.0.0.1:8001',
    situacao: 'Conectado',
    ultimaTroca: '2 min',
  },
  {
    id: 'tefe',
    nome: 'Polo Tefé',
    endereco: '127.0.0.1:8005',
    situacao: 'Conectado',
    ultimaTroca: '5 min',
  },
]

export const usoDiarioExemplo: UsoDiario[] = [
  { dia: '28/10', ampolas: 24 },
  { dia: '29/10', ampolas: 38 },
  { dia: '30/10', ampolas: 18 },
  { dia: '31/10', ampolas: 42 },
  { dia: '01/11', ampolas: 30 },
  { dia: '02/11', ampolas: 54 },
  { dia: '03/11', ampolas: 36 },
]