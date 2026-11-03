"""Testes do núcleo: diário, regras de estoque, remessas, surto, rotas e sincronização HTTP."""
import itertools
import json
import random
import shutil
import tempfile
import time
import unittest
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from soro import surto
from soro.config import carregar
from soro.diario import Diario
from soro.no import ErroNegocio, No
from soro.rotas import postos_criticos

CONFIG = Path(__file__).resolve().parent.parent / "redes" / "amazonas.json"
HOJE = date(2026, 11, 1)


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.rede = carregar(CONFIG)

    def tearDown(self):
        shutil.rmtree(self.pasta, ignore_errors=True)

    def no(self, uid, subpasta=None):
        return No(self.rede, uid, Path(self.pasta) / (subpasta or uid), hoje=lambda: HOJE)


def trocar(a: No, b: No):
    """Uma rodada de sincronização entre dois nós, sem rede (mesma lógica do HTTP)."""
    a.diario.incorporar(b.diario.desde(a.diario.vetor()))
    b.diario.incorporar(a.diario.desde(b.diario.vetor()))


class TestDiario(Base):
    def test_so_aceita_prefixo_continuo(self):
        d = Diario(Path(self.pasta) / "x.db", "x")
        evs = [{"origem": "a", "seq": s, "tipo": "t", "chave": str(s), "dados": {}, "quando": 1.0} for s in (1, 2, 3)]
        self.assertEqual(len(d.incorporar([evs[0], evs[2]])), 1)   # o 3 tem buraco antes
        self.assertEqual(d.vetor(), {"a": 1})
        self.assertEqual(len(d.incorporar(evs)), 2)                 # repetido é ignorado
        self.assertEqual(d.vetor(), {"a": 3})

    def test_qualquer_ordem_de_troca_converge(self):
        for semente in range(5):
            rng = random.Random(semente)
            nos = [Diario(Path(self.pasta) / f"{semente}-{i}.db", f"n{i}") for i in range(4)]
            for _ in range(60):
                n = rng.choice(nos)
                n.acrescentar("t", str(rng.random()), {"v": rng.randint(1, 9)})
                if rng.random() < 0.3:
                    a, b = rng.sample(nos, 2)
                    a.incorporar(b.desde(a.vetor()))
            for a, b in itertools.permutations(nos, 2):
                a.incorporar(b.desde(a.vetor()))
            for a, b in itertools.permutations(nos, 2):
                a.incorporar(b.desde(a.vetor()))
            self.assertEqual(len({n.resumo() for n in nos}), 1)


class TestEstoque(Base):
    def test_saida_pelo_lote_que_vence_antes_e_vencido_bloqueado(self):
        n = self.no("benjamin")
        n.registrar_entrada("SAB", "VENCIDO", (HOJE - timedelta(days=1)).isoformat(), 5)
        n.registrar_entrada("SAB", "NOVO", "2027-12-31", 20)
        n.registrar_entrada("SAB", "VELHO", "2027-01-31", 6)
        self.assertEqual(n.disponivel("benjamin", "SAB"), 26)
        caso = n.atender("botropico", "moderado", 8)
        self.assertEqual(caso["soro"], "SAB")
        saldos = {l["lote"]: l["qtd"] for l in n.lotes("benjamin")}
        self.assertEqual(saldos, {"VENCIDO": 5, "NOVO": 18})

    def test_sem_soro_suficiente_sugere_destino(self):
        n = self.no("atalaia")
        n.registrar_entrada("SAB", "L1", "2027-12-31", 3)
        caso = n.atender("botropico", "grave", 12)
        self.assertFalse(caso["atendido"])
        self.assertEqual(n.disponivel("atalaia", "SAB"), 3)

    def test_caso_repetido_nao_duplica(self):
        n = self.no("benjamin")
        n.atender("escorpionico", "leve", 0, caso_id="abc")
        self.assertTrue(n.atender("escorpionico", "leve", 0, caso_id="abc")["repetido"])
        self.assertEqual(len(n.casos()), 1)

    def test_capacidade_da_geladeira(self):
        n = self.no("benjamin")
        with self.assertRaises(ErroNegocio):
            n.registrar_entrada("SAB", "L1", "2027-12-31", 121)


class TestRemessas(Base):
    def test_em_transito_conta_e_capacidade_limita(self):
        polo, posto = self.no("tabatinga"), self.no("atalaia")
        polo.registrar_entrada("SAB", "P1", "2027-12-31", 150)
        r = polo.enviar_remessa("atalaia", "SAB", 30)
        sug = {s["soro"]: s for s in polo.sugestoes() if s["unidade"] == "atalaia"}
        self.assertEqual(sug["SAB"]["a_caminho"], 30)
        self.assertEqual(sug["SAB"]["sugestao"], 0)
        with self.assertRaises(ErroNegocio):
            polo.enviar_remessa("atalaia", "SAB", 100)   # não cabe: 120 - 30 a caminho
        trocar(polo, posto)
        posto.receber_remessa(r["id"])
        self.assertEqual(posto.disponivel("atalaia", "SAB"), 30)
        trocar(polo, posto)
        self.assertEqual(polo.em_transito("atalaia"), [])
        self.assertEqual(polo.disponivel("atalaia", "SAB"), 30)


class TestSurto(Base):
    def test_c2(self):
        contagens = Counter({HOJE - timedelta(days=i): 1 for i in range(1, 15)})
        contagens[HOJE] = 6
        r = surto.c2(contagens, HOJE)
        self.assertTrue(r["alarme"])
        self.assertAlmostEqual(r["limiar"], 4.0)
        contagens[HOJE] = 3
        self.assertFalse(surto.c2(contagens, HOJE)["alarme"])

    def test_sem_historico_nao_alarma(self):
        self.assertFalse(surto.c2(Counter({HOJE: 10}), HOJE)["alarme"])

    def test_polo_e_secretaria_geram_o_mesmo_alerta(self):
        polo, fvs = self.no("tabatinga"), self.no("fvs")
        for i in range(1, 15):
            polo.atender("escorpionico", "leve", 0, data=(HOJE - timedelta(days=i)).isoformat())
        for _ in range(7):
            polo.atender("escorpionico", "leve", 0)
        trocar(polo, fvs)
        a1, a2 = polo.vigiar(), fvs.vigiar()
        self.assertEqual(a1[0]["id"], a2[0]["id"])
        trocar(polo, fvs)
        self.assertEqual(len(fvs.alertas_ativos("Alto Solimões")), 1)


class TestRotas(Base):
    def test_onde_tem_soro_ordena_por_tempo(self):
        n = self.no("fvs")
        n.registrar_entrada("SAB", "F1", "2027-12-31", 50)
        destinos = n.onde_tem_soro("itaquai", ["SAB"])
        self.assertEqual(destinos[0]["unidade"], "fvs")
        self.assertGreater(destinos[0]["horas"], 6)
        self.assertTrue(destinos[0]["acima_do_limite"])

    def test_criticos_paralelo_igual_sequencial(self):
        adj = {"a": [("p1", 1, "x")], "p1": [("a", 1, "x"), ("p2", 2, "x")],
               "p2": [("p1", 2, "x"), ("b", 5, "x")], "b": [("p2", 5, "x")]}
        r1, _ = postos_criticos(adj, ["a", "b"], ["p1", "p2"], 5.5, 1)
        r2, _ = postos_criticos(adj, ["a", "b"], ["p1", "p2"], 5.5, 2)
        self.assertEqual(r1, r2)
        self.assertEqual(r1, {"p1": 0, "p2": 1})


class TestGraficos(Base):
    def test_uso_casos_e_vencimento(self):
        n = self.no("benjamin")
        n.registrar_entrada("SAB", "CEDO", "2026-12-15", 10)
        n.registrar_entrada("SAB", "TARDE", "2027-12-31", 20)
        n.atender("botropico", "moderado", 8)
        g = n.graficos(30)
        self.assertEqual(g["dias"][-1], HOJE.isoformat())
        self.assertEqual(g["uso_diario"]["SAB"][-1], 8)
        self.assertEqual(g["casos_por_regiao"][0]["agravos"]["botropico"], 1)
        vence = {m["mes"]: m["soros"]["SAB"] for m in g["vencimento_mensal"]}
        self.assertEqual((vence["2026-12"], vence["2027-12"]), (2, 20))


class TestCnes(Base):
    def test_dados_do_cnes_chegam_a_rota(self):
        pasta = Path(self.pasta)
        shutil.copy(CONFIG, pasta / "rede.json")
        (pasta / "rede.cnes.json").write_text(json.dumps({"2016125": {
            "cnes": "2016125", "nome": "Hospital de Guarnicao de Tabatinga", "endereco": "Avenida da Amizade 887",
            "telefone": "(97) 34122403", "lat": -4.25, "lon": -69.94}}), encoding="utf-8")
        self.rede = carregar(pasta / "rede.json")
        self.assertEqual(self.rede.unidade("tabatinga").estabelecimento["telefone"], "(97) 34122403")
        n = self.no("tabatinga")
        n.registrar_entrada("SAB", "T1", "2027-12-31", 30)
        d = n.onde_tem_soro("benjamin", ["SAB"])[0]
        self.assertEqual((d["estabelecimento"]["nome"], d["lat"], d["lon"]), ("Hospital de Guarnicao de Tabatinga", -4.25, -69.94))


class TestHTTP(Base):
    """Dois nós de verdade, cada um com servidor HTTP, sincronizando pela rede local."""

    def test_caso_registrado_num_no_chega_ao_vizinho(self):
        from soro.servidor import ServidorNo
        for i, u in enumerate(self.rede.unidades.values()):
            u.porta = 19100 + i
        a, b = self.no("benjamin"), self.no("atalaia")
        sa, sb = ServidorNo(a, intervalo_sync=0.2), ServidorNo(b, intervalo_sync=0.2)
        sa.iniciar(bloquear=False)
        sb.iniciar(bloquear=False)
        try:
            req = urllib.request.Request(a.u.url + "/api/casos", method="POST",
                                         data=b'{"agravo":"escorpionico","ampolas":0,"id":"x1"}',
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
            fim = time.time() + 5
            while time.time() < fim and not b.casos():
                time.sleep(0.05)
            self.assertEqual([c["id"] for c in b.casos()], ["x1"])
        finally:
            sa.parar()
            sb.parar()


if __name__ == "__main__":
    unittest.main()
