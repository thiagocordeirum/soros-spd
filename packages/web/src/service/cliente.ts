export class ErroHttp extends Error {
  public readonly status: number

  constructor(
    status: number,
    mensagem: string,
  ) {
    super(mensagem)
    this.status = status
    this.name = 'ErroHttp'
  }
}

function extrairMensagem(dados: unknown): string | null {
  if (
    typeof dados === 'object' &&
    dados !== null &&
    'erro' in dados &&
    typeof dados.erro === 'string'
  ) {
    return dados.erro
  }

  return null
}

export async function requisitar<T>(
  caminho: string,
  opcoes: RequestInit = {},
): Promise<T> {
  const headers = new Headers(opcoes.headers)

  headers.set('Accept', 'application/json')

  if (opcoes.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  const controlador = new AbortController()
  const timeout = window.setTimeout(() => controlador.abort(), 10_000)

  try {
    const resposta = await fetch(`/api${caminho}`, {
      ...opcoes,
      headers,
      credentials: 'same-origin',
      cache: 'no-store',
      signal: controlador.signal,
    })

    const texto = await resposta.text()
    let dados: unknown = null

    if (texto) {
      try {
        dados = JSON.parse(texto)
      } catch {
        throw new ErroHttp(
          resposta.status,
          'O servidor retornou uma resposta inválida. Confira se a API está disponível.',
        )
      }
    }

    if (!resposta.ok) {
      throw new ErroHttp(
        resposta.status,
        extrairMensagem(dados) ??
          `Não foi possível concluir a operação (${resposta.status}).`,
      )
    }

    return dados as T
  } catch (erro) {
    if (erro instanceof ErroHttp) {
      throw erro
    }

    if (controlador.signal.aborted) {
      throw new Error(
        'O servidor demorou para responder. Tente novamente.',
      )
    }

    throw new Error(
      'Não foi possível conectar ao servidor. Confira a conexão e tente novamente.',
    )
  } finally {
    window.clearTimeout(timeout)
  }
}