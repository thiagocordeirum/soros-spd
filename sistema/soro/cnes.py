"""Dados reais dos estabelecimentos, vindos do CNES pela API de Dados Abertos do Ministério da Saúde.

Cada unidade do arquivo da rede pode ter o código CNES do hospital ou da unidade
de saúde que guarda o soro. Este módulo consulta a API pública (sem chave) e grava
nome, endereço, telefone e coordenadas num arquivo ao lado da configuração
(``redes/amazonas.cnes.json``). Os nós leem esse arquivo ao subir; com o sistema
rodando ninguém chama a API, então o posto continua funcionando sem internet.
"""
from __future__ import annotations

import json
import time
import urllib.request

from .config import Rede, arquivo_cnes

API = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/{}"


PEQUENAS = {"de", "da", "do", "das", "dos", "e"}
ROMANOS = {"i", "ii", "iii", "iv", "v", "vi"}


def _legivel(texto: str | None) -> str | None:
    """O CNES grava tudo em maiúsculas e sem acento; deixa só as iniciais maiúsculas."""
    if not texto:
        return texto
    palavras = texto.lower().split()
    return " ".join(p if (i and p in PEQUENAS) or p.rstrip(",") == "s/n" else p.upper() if p in ROMANOS else p.capitalize()
                    for i, p in enumerate(palavras))


def consultar(codigo: str, timeout: float = 20) -> dict:
    req = urllib.request.Request(API.format(codigo), headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    endereco = " ".join(str(x) for x in (d.get("endereco_estabelecimento"), d.get("numero_estabelecimento")) if x)
    if d.get("bairro_estabelecimento"):
        endereco += ", " + d["bairro_estabelecimento"]
    return {"cnes": str(d["codigo_cnes"]), "nome": _legivel(d.get("nome_fantasia") or d.get("nome_razao_social")),
            "endereco": _legivel(endereco), "cep": d.get("codigo_cep_estabelecimento"),
            "telefone": d.get("numero_telefone_estabelecimento"),
            "lat": d.get("latitude_estabelecimento_decimo_grau"), "lon": d.get("longitude_estabelecimento_decimo_grau"),
            "consultado_em": time.strftime("%Y-%m-%d")}


def importar(rede: Rede) -> dict:
    """Baixa os dados de todas as unidades com código CNES e grava o arquivo da rede."""
    saida = {}
    for u in rede.unidades.values():
        if not u.cnes:
            print(f"  {u.nome}: sem código CNES no arquivo da rede")
            continue
        try:
            saida[u.cnes] = consultar(u.cnes)
            e = saida[u.cnes]
            print(f"  {u.nome}: {e['nome']} ({e['lat']}, {e['lon']})")
        except Exception as erro:  # um código ruim não impede os outros
            print(f"  {u.nome}: falhou ({erro})")
    destino = arquivo_cnes(rede.arquivo)
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Gravado em {destino}")
    return saida
