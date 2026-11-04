import type { 
  DadosPainel, 
  GraficosApi, 
  InformacoesPainelApi, 
  PainelApi, 
  RemessasApi 
} from "../domains/painel/types"
import { requisitar } from "./cliente"


export const painelService = {
  async carregar(): Promise<DadosPainel> {
    const [info, painel, graficos, remessas] = await Promise.all([
      requisitar<InformacoesPainelApi>('/info'),
      requisitar<PainelApi>('/painel'),
      requisitar<GraficosApi>('/graficos?dias=7'),
      requisitar<RemessasApi>('/remessas'),
    ])

    return {
      info,
      painel,
      graficos,
      remessas,
    }
  },
}