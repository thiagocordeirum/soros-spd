import { requisitar } from "../../service/cliente"
import type 
{ 
  Credenciais, 
  InformacoesNo, 
  LoginResposta, 
  PrimeiraConta, 
  SessaoResposta, 
  UsuarioAutenticado 
} from "./types"


export const autenticacaoService = {
  consultarSessao() {
    return requisitar<SessaoResposta>('/sessao')
  },

  consultarNo() {
    return requisitar<InformacoesNo>('/info')
  },

  entrar(credenciais: Credenciais) {
    return requisitar<LoginResposta>('/entrar', {
      method: 'POST',
      body: JSON.stringify(credenciais),
    })
  },

  cadastrarPrimeiraConta(conta: PrimeiraConta) {
    return requisitar<UsuarioAutenticado>('/usuarios', {
      method: 'POST',
      body: JSON.stringify({
        ...conta,
        tipo: 'gestor',
      }),
    })
  },

  sair() {
    return requisitar<Record<string, never>>('/sair', {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },
}