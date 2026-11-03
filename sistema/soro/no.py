"""Regras de negócio de um nó (uma unidade da rede).

Toda operação grava eventos no diário local e retorna na hora, sem consultar
outro nó. O que o nó sabe das outras unidades vem da sincronização e pode estar
atrasado; por isso as telas mostram há quanto tempo cada dado foi atualizado.

Tipos de evento e o que guardam (campo ``dados``):

``mov``     movimento de estoque: unidade, soro, lote, validade, qtd (+ entra, - sai),
            motivo (entrada, dispensa, envio, recebimento, perda), ref, data
``caso``    atendimento: id, unidade, regiao, data, agravo, gravidade, soro, ampolas,
            local, atendido, encaminhado_para
``remessa`` envio entre unidades: id, origem, destino, soro, itens [{lote, validade, qtd}], qtd, pedido
``receb``   confirmação de recebimento: remessa, destino, qtd
``pedido``  pedido de soro ao fornecedor: id, unidade, para, soro, qtd
``alerta``  surto detectado: id, regiao, dia, observado, media, limiar, por
``usuario`` conta de uma pessoa da equipe: login, nome, tipo, unidade, sal, hash, iter,
            criado_por, data (ver ``usuarios.py``)
``usuario_alt`` mudança numa conta: id, login, em (hora), e ``ativo`` e/ou sal, hash, iter

Os registros feitos por alguém da equipe levam ``por`` com o login de quem fez.

Só a própria unidade grava movimentos do seu estoque (o envio é gravado por
quem envia, o recebimento por quem recebe). Com um único escritor por estoque e
uma trava dentro do nó, o saldo nunca fica negativo, mesmo com várias pessoas
usando o sistema ao mesmo tempo no posto.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import surto
from .config import Rede
from .usuarios import (LOGIN_VALIDO, SENHA_MINIMA, TIPOS, cifrar, confere, pode_cadastrar,
                       unidades_geridas)
from .diario import Diario
from .rotas import INF, Mapa, destinos_com_soro, postos_criticos


class ErroNegocio(Exception):
    """Operação recusada por uma regra do sistema; a mensagem vai para a tela."""


class No:
    def __init__(self, rede: Rede, uid: str, pasta_dados: str | Path, hoje=None):
        self.rede = rede
        self.u = rede.unidade(uid)
        self.diario = Diario(Path(pasta_dados) / f"{uid}.db", uid)
        self.mapa = Mapa(rede.localidades, rede.trechos)
        self._trava = threading.RLock()
        self._cache_versao = -1
        self._cache = None
        self._hoje = hoje or date.today

    # --- utilidades ---------------------------------------------------------
    def hoje(self) -> date:
        return self._hoje()

    def _visao(self) -> dict:
        """Estado atual calculado a partir dos eventos (refeito só quando chega evento novo)."""
        if self._cache_versao == self.diario.versao and self._cache is not None:
            return self._cache
        versao = self.diario.versao
        lotes: dict[tuple[str, str], dict] = {}
        dispensas: list[tuple[str, str, date, int]] = []
        unicos: dict[str, dict[str, dict]] = defaultdict(dict)
        for ev in self.diario.eventos():
            d, tipo = ev["dados"], ev["tipo"]
            if tipo == "mov":
                k = (d["unidade"], d["lote"])
                lote = lotes.setdefault(k, {"unidade": d["unidade"], "lote": d["lote"], "soro": d["soro"],
                                            "validade": d["validade"], "qtd": 0})
                lote["qtd"] += d["qtd"]
                if d["motivo"] == "dispensa":
                    dispensas.append((d["unidade"], d["soro"], date.fromisoformat(d["data"]), -d["qtd"]))
            elif ev["chave"] not in unicos[tipo]:
                # Mesmo id criado em dois nós (ex.: alerta do polo e da secretaria): fica o primeiro na ordem do diário.
                unicos[tipo][ev["chave"]] = d
        # Contas: vale a criação mais antiga de cada login; mudanças entram pela hora em que foram feitas.
        usuarios = {k: {**d, "ativo": True} for k, d in unicos["usuario"].items()}
        for alt in sorted(unicos["usuario_alt"].values(), key=lambda a: (a["em"], a["id"])):
            if alt["login"] in usuarios:
                usuarios[alt["login"]].update({k: alt[k] for k in ("ativo", "sal", "hash", "iter") if k in alt})
        self._cache = {"lotes": lotes, "dispensas": dispensas, "casos": unicos["caso"],
                       "remessas": unicos["remessa"], "recebimentos": unicos["receb"],
                       "pedidos": unicos["pedido"], "alertas": unicos["alerta"], "usuarios": usuarios}
        self._cache_versao = versao
        return self._cache

    def _soro_valido(self, soro: str) -> None:
        if soro not in self.rede.soros:
            raise ErroNegocio(f"Soro desconhecido: {soro}")

    @staticmethod
    def _qtd(valor) -> int:
        try:
            qtd = int(valor)
        except (TypeError, ValueError):
            raise ErroNegocio("Quantidade inválida")
        if qtd <= 0:
            raise ErroNegocio("A quantidade precisa ser maior que zero")
        return qtd

    # --- estoque ------------------------------------------------------------
    def lotes(self, unidade: str | None = None, soro: str | None = None) -> list[dict]:
        """Lotes com saldo, do que vence primeiro ao último (FEFO)."""
        unidade = unidade or self.u.id
        hoje = self.hoje()
        saida = []
        for l in self._visao()["lotes"].values():
            if l["unidade"] != unidade or l["qtd"] <= 0 or (soro and l["soro"] != soro):
                continue
            dias = (date.fromisoformat(l["validade"]) - hoje).days
            saida.append({**l, "vence_em_dias": dias, "vencido": dias < 0})
        return sorted(saida, key=lambda l: (l["validade"], l["lote"]))

    def disponivel(self, unidade: str, soro: str) -> int:
        return sum(l["qtd"] for l in self.lotes(unidade, soro) if not l["vencido"])

    def total_estoque(self, unidade: str) -> int:
        return sum(l["qtd"] for l in self.lotes(unidade))

    def em_transito(self, destino: str | None = None, soro: str | None = None) -> list[dict]:
        v = self._visao()
        return [r for rid, r in v["remessas"].items()
                if rid not in v["recebimentos"] and (destino is None or r["destino"] == destino)
                and (soro is None or r["soro"] == soro)]

    def espaco_livre(self, unidade: str) -> int:
        cap = self.rede.unidade(unidade).capacidade
        return cap - self.total_estoque(unidade) - sum(r["qtd"] for r in self.em_transito(unidade))

    def registrar_entrada(self, soro: str, lote: str, validade: str, qtd, por: str | None = None) -> dict:
        """Entrada de lote vindo de fora da rede (por exemplo, a cota do Ministério)."""
        self._soro_valido(soro)
        qtd = self._qtd(qtd)
        lote = str(lote).strip()
        if not lote:
            raise ErroNegocio("Informe o número do lote")
        try:
            date.fromisoformat(validade)
        except (TypeError, ValueError):
            raise ErroNegocio("Validade deve estar no formato AAAA-MM-DD")
        with self._trava:
            if qtd > self.espaco_livre(self.u.id):
                raise ErroNegocio(f"Não cabe na geladeira: espaço livre de {self.espaco_livre(self.u.id)} ampolas")
            ev = self.diario.acrescentar("mov", f"{self.u.id}|{lote}", {
                "unidade": self.u.id, "soro": soro, "lote": lote, "validade": validade, "qtd": qtd,
                "motivo": "entrada", "ref": None, "data": self.hoje().isoformat(), "por": por})
        return ev["dados"]

    def _baixar(self, soro: str, qtd: int, motivo: str, ref: str, data: str) -> list[dict]:
        """Saída pelo lote que vence primeiro. Chamar com a trava do nó."""
        itens, resto = [], qtd
        for l in self.lotes(self.u.id, soro):
            if l["vencido"]:
                continue
            usar = min(l["qtd"], resto)
            self.diario.acrescentar("mov", f"{self.u.id}|{l['lote']}", {
                "unidade": self.u.id, "soro": soro, "lote": l["lote"], "validade": l["validade"],
                "qtd": -usar, "motivo": motivo, "ref": ref, "data": data})
            itens.append({"lote": l["lote"], "validade": l["validade"], "qtd": usar})
            resto -= usar
            if resto == 0:
                break
        return itens

    def registrar_perda(self, lote: str, qtd, motivo: str = "perda", por: str | None = None) -> dict:
        qtd = self._qtd(qtd)
        with self._trava:
            atual = next((l for l in self.lotes(self.u.id) if l["lote"] == lote), None)
            if atual is None or atual["qtd"] < qtd:
                raise ErroNegocio("Lote sem saldo suficiente")
            ev = self.diario.acrescentar("mov", f"{self.u.id}|{lote}", {
                "unidade": self.u.id, "soro": atual["soro"], "lote": lote, "validade": atual["validade"],
                "qtd": -qtd, "motivo": motivo, "ref": None, "data": self.hoje().isoformat(), "por": por})
        return ev["dados"]

    # --- atendimento --------------------------------------------------------
    def atender(self, agravo: str, gravidade: str, ampolas, local: str | None = None,
                caso_id: str | None = None, data: str | None = None, por: str | None = None) -> dict:
        """Registra um caso e dá baixa no soro aplicado.

        ``caso_id`` é gerado pelo navegador; se o mesmo caso for enviado de novo
        (por exemplo, depois de uma falha de rede), o sistema não grava duas vezes.
        """
        if agravo not in self.rede.agravos:
            raise ErroNegocio(f"Agravo desconhecido: {agravo}")
        try:
            ampolas = int(ampolas)
        except (TypeError, ValueError):
            raise ErroNegocio("Número de ampolas inválido")
        if ampolas < 0:
            raise ErroNegocio("Número de ampolas inválido")
        data = data or self.hoje().isoformat()
        try:
            if date.fromisoformat(data) > self.hoje():
                raise ErroNegocio("A data do atendimento não pode ser futura")
        except ValueError:
            raise ErroNegocio("Data deve estar no formato AAAA-MM-DD")
        caso_id = caso_id or uuid.uuid4().hex
        local = local or self.u.local
        with self._trava:
            existente = self._visao()["casos"].get(caso_id)
            if existente:
                return {**existente, "repetido": True}
            soros = self.rede.agravos[agravo]["soros"]
            usado = None
            if ampolas > 0:
                usado = next((s for s in soros if self.disponivel(self.u.id, s) >= ampolas), None)
            caso = {"id": caso_id, "unidade": self.u.id, "regiao": self.u.regiao, "data": data,
                    "agravo": agravo, "gravidade": gravidade, "soro": usado, "ampolas": ampolas if usado else 0,
                    "local": local, "atendido": bool(usado) or ampolas == 0, "encaminhado_para": None, "por": por}
            if ampolas > 0 and not usado:
                destinos = self.onde_tem_soro(self.u.local, soros, ampolas, excluir=self.u.id)
                caso["encaminhado_para"] = destinos[0]["unidade"] if destinos else None
            if usado:
                self._baixar(usado, ampolas, "dispensa", caso_id, data)
            self.diario.acrescentar("caso", caso_id, caso)
        if ampolas > 0 and not usado:
            caso["sugestoes"] = destinos[:3]
        return caso

    def casos(self, regiao: str | None = None, unidade: str | None = None) -> list[dict]:
        cs = self._visao()["casos"].values()
        return sorted((c for c in cs if (regiao is None or c["regiao"] == regiao)
                       and (unidade is None or c["unidade"] == unidade)),
                      key=lambda c: (c["data"], c["id"]), reverse=True)

    # --- remessas e pedidos -------------------------------------------------
    def enviar_remessa(self, destino: str, soro: str, qtd, pedido: str | None = None, por: str | None = None) -> dict:
        self._soro_valido(soro)
        qtd = self._qtd(qtd)
        if destino == self.u.id:
            raise ErroNegocio("O destino precisa ser outra unidade")
        self.rede.unidade(destino)
        with self._trava:
            if self.disponivel(self.u.id, soro) < qtd:
                raise ErroNegocio(f"Estoque insuficiente: há {self.disponivel(self.u.id, soro)} ampolas de {soro}")
            livre = self.espaco_livre(destino)
            if qtd > livre:
                raise ErroNegocio(f"Não cabe no destino: espaço livre visto de {livre} ampolas")
            rid = uuid.uuid4().hex[:12]
            data = self.hoje().isoformat()
            itens = self._baixar(soro, qtd, "envio", rid, data)
            remessa = {"id": rid, "origem": self.u.id, "destino": destino, "soro": soro,
                       "itens": itens, "qtd": qtd, "pedido": pedido, "data": data, "por": por}
            self.diario.acrescentar("remessa", rid, remessa)
        return remessa

    def receber_remessa(self, remessa_id: str, qtd_recebida=None, por: str | None = None) -> dict:
        with self._trava:
            v = self._visao()
            r = v["remessas"].get(remessa_id)
            if r is None:
                raise ErroNegocio("Remessa ainda não chegou a esta unidade pela sincronização")
            if r["destino"] != self.u.id:
                raise ErroNegocio("Esta remessa é de outra unidade")
            if remessa_id in v["recebimentos"]:
                raise ErroNegocio("Remessa já recebida")
            recebido = r["qtd"] if qtd_recebida in (None, "") else int(qtd_recebida)
            if not 0 <= recebido <= r["qtd"]:
                raise ErroNegocio("Quantidade recebida inválida")
            if recebido > self.espaco_livre(self.u.id) + r["qtd"]:
                raise ErroNegocio("Não cabe na geladeira")
            data = self.hoje().isoformat()
            resto = recebido
            for item in r["itens"]:
                usar = min(item["qtd"], resto)
                if usar:
                    self.diario.acrescentar("mov", f"{self.u.id}|{item['lote']}", {
                        "unidade": self.u.id, "soro": r["soro"], "lote": item["lote"],
                        "validade": item["validade"], "qtd": usar, "motivo": "recebimento",
                        "ref": remessa_id, "data": data})
                resto -= usar
            receb = {"remessa": remessa_id, "destino": self.u.id, "qtd": recebido,
                     "divergencia": r["qtd"] - recebido, "data": data, "por": por}
            self.diario.acrescentar("receb", remessa_id, receb)
        return receb

    def pedir(self, soro: str, qtd, por: str | None = None) -> dict:
        self._soro_valido(soro)
        qtd = self._qtd(qtd)
        if not self.u.pai:
            raise ErroNegocio("Esta unidade não tem fornecedor na rede")
        pid = uuid.uuid4().hex[:12]
        pedido = {"id": pid, "unidade": self.u.id, "para": self.u.pai, "soro": soro, "qtd": qtd,
                  "data": self.hoje().isoformat(), "por": por}
        self.diario.acrescentar("pedido", pid, pedido)
        return pedido

    def pedidos_abertos(self, para: str | None = None) -> list[dict]:
        v = self._visao()
        atendidos = {r["pedido"] for r in v["remessas"].values() if r.get("pedido")}
        return [p for p in v["pedidos"].values()
                if p["id"] not in atendidos and (para is None or p["para"] == para)]

    def alvo(self, unidade: str, soro: str) -> int:
        u = self.rede.unidade(unidade)
        base = u.alvo.get(soro, 0)
        return base * 2 if u.regiao and self.alertas_ativos(u.regiao) else base

    def sugestoes(self) -> list[dict]:
        """Quanto mandar para cada unidade abastecida por esta.

        Conta o que o destino tem (segundo a última informação) mais o que já
        está a caminho, e nunca passa do espaço livre da geladeira dele.
        """
        linhas = []
        for filho in self.u.abastece:
            for soro in self.rede.unidade(filho).alvo:
                alvo = self.alvo(filho, soro)
                tem = self.disponivel(filho, soro)
                caminho = sum(r["qtd"] for r in self.em_transito(filho, soro))
                livre = self.espaco_livre(filho)
                meu = self.disponivel(self.u.id, soro)
                if tem + caminho >= alvo * 0.5:
                    qtd, motivo = 0, "estoque suficiente"
                elif caminho:
                    qtd, motivo = 0, "aguardando remessa a caminho"
                else:
                    qtd = max(0, min(alvo - tem - caminho, livre, meu))
                    motivo = "limitado pelo espaço livre" if qtd == livre else (
                        "limitado pelo estoque daqui" if qtd == meu else "até o estoque-alvo")
                linhas.append({"unidade": filho, "nome": self.rede.unidade(filho).nome, "soro": soro,
                               "tem": tem, "a_caminho": caminho, "cabe": livre, "alvo": alvo,
                               "sugestao": qtd, "motivo": motivo,
                               "atualizado_ha_s": self.idade(filho)})
        return linhas

    # --- vigilância ---------------------------------------------------------
    def regioes_vigiadas(self) -> list[str]:
        if self.u.nivel == "estado":
            return list(self.rede.regioes)
        if self.u.nivel == "polo" and self.u.regiao:
            return [self.u.regiao]
        return []

    def alertas_ativos(self, regiao: str | None = None) -> list[dict]:
        vale = int(self.rede.param("alerta_vale_dias", 7))
        hoje = self.hoje()
        return [a for a in self._visao()["alertas"].values()
                if (regiao is None or a["regiao"] == regiao)
                and 0 <= (hoje - date.fromisoformat(a["dia"])).days < vale]

    def vigiar(self) -> list[dict]:
        """Roda o C2 sobre os casos que este nó conhece e emite alertas novos."""
        novos = []
        hoje = self.hoje()
        for regiao in self.regioes_vigiadas():
            if self.alertas_ativos(regiao):
                continue
            contagens = surto.casos_por_dia(self.casos(regiao))
            for atraso in range(3):
                r = surto.c2(contagens, hoje - timedelta(days=atraso))
                if r["alarme"]:
                    dia = date.fromisoformat(r["dia"])
                    alerta = {"id": surto.id_alerta(regiao, dia), "regiao": regiao, "dia": r["dia"],
                              "observado": r["observado"], "media": r["media"], "limiar": r["limiar"],
                              "por": self.u.id}
                    with self._trava:
                        if alerta["id"] not in self._visao()["alertas"]:
                            self.diario.acrescentar("alerta", alerta["id"], alerta)
                            novos.append(alerta)
                    break
        return novos

    def serie_regiao(self, regiao: str, dias: int = 14) -> list[dict]:
        return surto.serie(surto.casos_por_dia(self.casos(regiao)), self.hoje(), dias)

    # --- painel -------------------------------------------------------------
    def unidades_visiveis(self) -> list[str]:
        if self.u.nivel == "estado":
            return list(self.rede.unidades)
        if self.u.nivel == "polo":
            return [self.u.id] + self.u.abastece
        return [self.u.id]

    def idade(self, unidade: str) -> float | None:
        """Segundos desde a última informação recebida de ``unidade``."""
        if unidade == self.u.id:
            return 0.0
        quando = self.diario.contatos().get(unidade)
        return None if quando is None else max(0.0, time.time() - quando)

    def uso_mensal(self, unidade: str, soro: str, dias: int = 90) -> float:
        inicio = self.hoje() - timedelta(days=dias)
        total = sum(q for u, s, d, q in self._visao()["dispensas"] if u == unidade and s == soro and d >= inicio)
        return round(total * 30 / dias, 1)

    def painel(self) -> dict:
        linhas = []
        for uid in self.unidades_visiveis():
            u = self.rede.unidade(uid)
            por_soro = []
            for soro in self.rede.soros:
                tem = self.disponivel(uid, soro)
                uso = self.uso_mensal(uid, soro)
                if tem == 0 and uso == 0 and soro not in u.alvo:
                    continue
                por_soro.append({"soro": soro, "estoque": tem, "uso_mes": uso,
                                 "dura_meses": round(tem / uso, 1) if uso else None})
            linhas.append({"unidade": uid, "nome": u.nome, "nivel": u.nivel, "regiao": u.regiao,
                           "total": self.total_estoque(uid), "capacidade": u.capacidade,
                           "a_caminho": sum(r["qtd"] for r in self.em_transito(uid)),
                           "atualizado_ha_s": self.idade(uid), "soros": por_soro})
        return {"unidades": linhas, "vencendo": self.vencimentos(),
                "alertas": self.alertas_ativos(), "pedidos": self.pedidos_abertos(self.u.id)}

    def graficos(self, dias: int = 30, unidade: str | None = None) -> dict:
        """Séries para os gráficos das telas, sobre as unidades que este nó acompanha (ou uma delas)."""
        visiveis = set(self.unidades_visiveis())
        if unidade in visiveis:
            visiveis = {unidade}
        hoje = self.hoje()
        datas = [hoje - timedelta(days=i) for i in range(dias - 1, -1, -1)]
        pos = {d: i for i, d in enumerate(datas)}
        uso = {s: [0] * dias for s in self.rede.soros}
        for u, soro, d, q in self._visao()["dispensas"]:
            if u in visiveis and d in pos:
                uso[soro][pos[d]] += q
        casos: dict[str, dict[str, int]] = {}
        for c in self._visao()["casos"].values():
            if c["unidade"] in visiveis and date.fromisoformat(c["data"]) >= datas[0]:
                linha = casos.setdefault(c["regiao"] or "fora das regiões", {a: 0 for a in self.rede.agravos})
                linha[c["agravo"]] = linha.get(c["agravo"], 0) + 1
        meses = []
        for i in range(18):
            a, m = divmod(hoje.month - 1 + i, 12)
            meses.append(f"{hoje.year + a}-{m + 1:02d}")
        vence = {m: {s: 0 for s in self.rede.soros} for m in meses}
        for uid in visiveis:
            for l in self.lotes(uid):
                if not l["vencido"] and l["validade"][:7] in vence:
                    vence[l["validade"][:7]][l["soro"]] += l["qtd"]
        return {"dias": [d.isoformat() for d in datas], "uso_diario": uso,
                "casos_por_regiao": [{"regiao": r, "agravos": a} for r, a in sorted(casos.items())],
                "vencimento_mensal": [{"mes": m, "soros": vence[m]} for m in meses]}

    def vencimentos(self) -> list[dict]:
        """Lotes perto de vencer e para onde vale mandar antes que vençam."""
        limite = int(self.rede.param("aviso_vencimento_dias", 60))
        visiveis = self.unidades_visiveis()
        saida = []
        for uid in visiveis:
            for l in self.lotes(uid):
                if l["vencido"] or l["vence_em_dias"] > limite:
                    continue
                melhor = None
                for outro in visiveis:
                    if outro == uid or self.rede.unidade(outro).nivel == "estado":
                        continue
                    uso = self.uso_mensal(outro, l["soro"])
                    if uso <= 0:
                        continue
                    dura = self.disponivel(outro, l["soro"]) / uso
                    cabe = self.espaco_livre(outro)
                    if cabe > 0 and (melhor is None or dura < melhor[1]):
                        melhor = (outro, dura, cabe)
                sug = None
                if melhor:
                    sug = {"para": melhor[0], "nome": self.rede.unidade(melhor[0]).nome,
                           "dura_meses": round(melhor[1], 1), "qtd": min(l["qtd"], melhor[2])}
                saida.append({**l, "nome": self.rede.unidade(uid).nome, "sugestao": sug})
        return sorted(saida, key=lambda l: l["vence_em_dias"])

    # --- rota até o soro ----------------------------------------------------
    def onde_tem_soro(self, origem_local: str, soros: list[str], ampolas: int = 1,
                      excluir: str | None = None) -> list[dict]:
        if origem_local not in self.rede.localidades:
            raise ErroNegocio("Localidade desconhecida")
        limite = float(self.rede.param("limite_acesso_h", 6))
        candidatos, estoques = {}, {}
        for uid, u in self.rede.unidades.items():
            if uid == excluir:
                continue
            tem = {s: self.disponivel(uid, s) for s in soros}
            if max(tem.values(), default=0) >= max(1, ampolas):
                candidatos[uid] = u.local
                estoques[uid] = tem
        destinos = destinos_com_soro(self.mapa, origem_local, candidatos)
        for d in destinos:
            u = self.rede.unidade(d["unidade"])
            loc = self.rede.localidades[u.local]
            e = u.estabelecimento or {}
            d.update({"nome": u.nome, "nivel": u.nivel, "estoque": estoques[d["unidade"]],
                      "atualizado_ha_s": self.idade(d["unidade"]), "acima_do_limite": d["horas"] > limite,
                      "estabelecimento": u.estabelecimento,
                      "lat": e.get("lat") or loc["lat"], "lon": e.get("lon") or loc["lon"]})
            for passo in d["trajeto"]:
                passo["de_nome"] = self.rede.localidades[passo["de"]]["nome"]
                passo["para_nome"] = self.rede.localidades[passo["para"]]["nome"]
        return destinos

    def criticos(self, soro: str, processos: int = 1) -> dict:
        self._soro_valido(soro)
        limite = float(self.rede.param("limite_acesso_h", 6))
        com_soro = {u.local: uid for uid, u in self.rede.unidades.items() if self.disponivel(uid, soro) > 0}
        locais_unidades = {u.local for u in self.rede.unidades.values()}
        comunidades = [l for l in self.rede.localidades if l not in locais_unidades]
        resultado, segundos = postos_criticos(dict(self.mapa.adj), comunidades, list(com_soro), limite, processos)
        linhas = sorted(({"unidade": com_soro[l], "nome": self.rede.unidade(com_soro[l]).nome, "comunidades": n}
                         for l, n in resultado.items()), key=lambda x: -x["comunidades"])
        return {"soro": soro, "limite_horas": limite, "processos": processos,
                "segundos": round(segundos, 4), "postos": linhas}

    # --- contas da equipe ---------------------------------------------------
    def usuario(self, login: str) -> dict | None:
        return self._visao()["usuarios"].get(login)

    def publico(self, conta: dict) -> dict:
        """Conta sem sal nem hash, para mandar às telas."""
        return {"login": conta["login"], "nome": conta["nome"], "tipo": conta["tipo"],
                "tipo_nome": TIPOS[conta["tipo"]]["nome"], "unidade": conta["unidade"],
                "unidade_nome": self.rede.unidade(conta["unidade"]).nome, "ativo": conta["ativo"],
                "criado_por": conta.get("criado_por"), "data": conta.get("data")}

    def usuarios(self, autor: dict) -> list[dict]:
        """Contas que ``autor`` administra, por unidade e nome."""
        geridas = unidades_geridas(self.rede, autor)
        return sorted((self.publico(c) for c in self._visao()["usuarios"].values()
                       if geridas is None or c["unidade"] in geridas),
                      key=lambda c: (c["unidade_nome"], c["nome"].lower()))

    def primeiro_acesso(self) -> bool:
        """Sem nenhuma conta na rede, a secretaria cria a primeira, de gestão, sem login."""
        return self.u.nivel == "estado" and not self._visao()["usuarios"]

    def cadastrar(self, login: str, nome: str, tipo: str, unidade: str, senha: str, autor: dict | None) -> dict:
        login, nome = str(login).strip().lower(), str(nome).strip()
        if not LOGIN_VALIDO.match(login):
            raise ErroNegocio("O login não pode ter espaço nem acento: use letras, números, ponto, hífen, sublinhado ou @ (pode ser o e-mail)")
        if not nome:
            raise ErroNegocio("Informe o nome")
        if tipo not in TIPOS:
            raise ErroNegocio(f"Tipo de conta desconhecido: {tipo}")
        if unidade not in self.rede.unidades:
            raise ErroNegocio(f"Unidade desconhecida: {unidade}")
        if self.rede.unidade(unidade).nivel not in TIPOS[tipo]["niveis"]:
            raise ErroNegocio(f"{TIPOS[tipo]['nome']} não existe em {self.rede.unidade(unidade).nome}")
        if len(senha) < SENHA_MINIMA:
            raise ErroNegocio(f"A senha precisa de pelo menos {SENHA_MINIMA} caracteres")
        with self._trava:
            if autor is None:
                if not self.primeiro_acesso() or tipo != "gestor" or unidade != self.u.id:
                    raise ErroNegocio("Só a primeira conta, de gestão estadual, pode ser criada sem login")
            elif not pode_cadastrar(self.rede, autor, tipo, unidade):
                raise ErroNegocio("Você não pode cadastrar esse tipo de conta nessa unidade")
            if self.usuario(login):
                raise ErroNegocio(f"O login {login} já existe")
            conta = {"login": login, "nome": nome, "tipo": tipo, "unidade": unidade, **cifrar(senha),
                     "criado_por": autor["login"] if autor else None, "data": self.hoje().isoformat()}
            self.diario.acrescentar("usuario", login, conta)
        return self.publico({**conta, "ativo": True})

    def _alterar(self, login: str, **mudanca) -> None:
        aid = uuid.uuid4().hex
        self.diario.acrescentar("usuario_alt", aid, {"id": aid, "login": login, "em": time.time(), **mudanca})

    def mudar_situacao(self, login: str, ativo: bool, autor: dict) -> dict:
        conta = self.usuario(login)
        if conta is None:
            raise ErroNegocio("Conta não encontrada")
        if not pode_cadastrar(self.rede, autor, conta["tipo"], conta["unidade"]):
            raise ErroNegocio("Você não administra essa conta")
        if login == autor["login"]:
            raise ErroNegocio("Você não pode desativar a própria conta")
        self._alterar(login, ativo=bool(ativo))
        return self.publico(self.usuario(login))

    def trocar_senha(self, login: str, atual: str, nova: str) -> None:
        conta = self.usuario(login)
        if conta is None or not confere(atual, conta):
            raise ErroNegocio("Senha atual incorreta")
        if len(nova) < SENHA_MINIMA:
            raise ErroNegocio(f"A senha precisa de pelo menos {SENHA_MINIMA} caracteres")
        self._alterar(login, **cifrar(nova))

    def autenticar(self, login: str, senha: str) -> dict:
        conta = self.usuario(str(login).strip().lower())
        if conta is None or not confere(senha, conta):
            raise ErroNegocio("Login ou senha incorretos")
        if not conta["ativo"]:
            raise ErroNegocio("Esta conta foi desativada")
        if conta["unidade"] != self.u.id:
            raise ErroNegocio(f"Esta conta é de {self.rede.unidade(conta['unidade']).nome}. "
                              "Entre pelo endereço dessa unidade.")
        return conta

    # --- estado do nó ---------------------------------------------------------
    def info(self) -> dict:
        u = self.u
        return {"id": u.id, "nome": u.nome, "nivel": u.nivel, "regiao": u.regiao, "local": u.local,
                "pai": u.pai, "abastece": u.abastece, "vizinhos": u.vizinhos, "capacidade": u.capacidade,
                "estado": self.rede.estado, "soros": self.rede.soros,
                "agravos": self.rede.agravos,
                "unidades": {k: {"nome": x.nome, "nivel": x.nivel, "url": x.url} for k, x in self.rede.unidades.items()},
                "hoje": self.hoje().isoformat()}
