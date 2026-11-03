"""Cliente da API de um nó que entra com login e senha, como uma pessoa da equipe.

Usado pelos dados de exemplo, pela avaliação e pelos testes. Guarda o cookie da
sessão e não passa por proxy: o nó está nesta máquina ou na rede local.
"""
from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.error
import urllib.request


class ErroApi(Exception):
    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status


class Cliente:
    def __init__(self, url: str, tempo_limite: float = 5.0):
        self.url = url.rstrip("/")
        self.tempo_limite = tempo_limite
        self._abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def _pedir(self, caminho: str, corpo: dict | None = None) -> dict:
        dados = None if corpo is None else json.dumps(corpo).encode()
        req = urllib.request.Request(self.url + caminho, data=dados, method="GET" if corpo is None else "POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with self._abridor.open(req, timeout=self.tempo_limite) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise ErroApi(e.code, json.loads(e.read() or b"{}").get("erro", str(e))) from None

    def obter(self, caminho: str) -> dict:
        return self._pedir(caminho)

    def postar(self, caminho: str, corpo: dict | None = None) -> dict:
        return self._pedir(caminho, corpo or {})

    def entrar(self, login: str, senha: str, esperar_s: float = 0) -> dict:
        """Faz login. Com ``esperar_s``, tenta de novo enquanto a conta ainda não chegou ao nó pela sincronização."""
        limite = time.time() + esperar_s
        while True:
            try:
                return self.postar("/api/entrar", {"login": login, "senha": senha})
            except ErroApi:
                if time.time() >= limite:
                    raise
                time.sleep(0.3)
