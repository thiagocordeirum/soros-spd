export type TipoUsuario = 'profissional' | 'coordenador' | 'gestor'

export type Permissao =
  | 'atender'
  | 'estoque'
  | 'enviar'
  | 'paineis'
  | 'usuarios'

export interface UsuarioAutenticado {
  login: string
  nome: string
  tipo: TipoUsuario
  tipo_nome: string
  unidade: string
  unidade_nome: string
  ativo: boolean
  criado_por: string | null
  data: string | null
}

export interface Credenciais {
  login: string
  senha: string
}

export interface SessaoResposta {
  usuario: UsuarioAutenticado | null
  pode: Permissao[]
  primeiro_acesso: boolean
  tipos: Record<
    TipoUsuario,
    {
      nome: string
      niveis: string[]
    }
  >
}

export interface LoginResposta {
  usuario: UsuarioAutenticado
}

export interface PrimeiraConta {
  login: string
  nome: string
  senha: string
  unidade: string
}

export interface InformacoesNo {
  id: string
  nome: string
  nivel: 'estado' | 'polo' | 'posto'
}