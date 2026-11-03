"""Propriedades que garantem a convergência: o merge é comutativo,
associativo e idempotente, e réplicas que viram as mesmas operações em
ordens diferentes terminam iguais."""
import itertools
import random
import unittest

from soro.crdt import EstadoReplica, GCounter, MapaMaximo, PNCounter


def replicas_com_operacoes(semente: int, n_replicas: int = 3, n_ops: int = 60):
    rng = random.Random(semente)
    replicas = [EstadoReplica() for _ in range(n_replicas)]
    for r in replicas:
        r.inventario.registrar_lote("L1", "SAB", 100)
        r.inventario.registrar_lote("L2", "SAB", 200)
    for i in range(n_ops):
        k = rng.randrange(n_replicas)
        r, nome = replicas[k], f"r{k}"
        op = rng.random()
        if op < 0.4:
            r.inventario.movimentar(nome, rng.choice(["A", "B"]), rng.choice(["L1", "L2"]), rng.randint(1, 20))
        elif op < 0.7:
            r.inventario.dispensar(nome, rng.choice(["A", "B"]), "SAB", rng.randint(1, 8), dia=0)
        elif op < 0.9:
            r.casos.adicionar(f"{nome}#{i}", {"id": f"{nome}#{i}", "dia": i})
        else:
            r.alertas.adicionar(f"surto:X:{i % 3}", {"id": f"surto:X:{i % 3}", "por": nome})
        if rng.random() < 0.2:  # sincronização parcial ocasional
            j = rng.randrange(n_replicas)
            replicas[j].merge(r)
    return replicas


def copia(e: EstadoReplica) -> EstadoReplica:
    return EstadoReplica.de_dict(e.para_dict())


class TestContadores(unittest.TestCase):
    def test_gcounter_merge_pega_maximo_por_replica(self):
        a, b = GCounter({"x": 3, "y": 1}), GCounter({"x": 1, "y": 5, "z": 2})
        a.merge(b)
        self.assertEqual(a.contagens, {"x": 3, "y": 5, "z": 2})
        self.assertEqual(a.valor, 10)

    def test_pncounter(self):
        c = PNCounter()
        c.somar("a", 10)
        c.somar("a", -4)
        c.somar("b", -1)
        self.assertEqual(c.valor, 5)


class TestPropriedadesDoMerge(unittest.TestCase):
    def test_comutativo(self):
        for s in range(20):
            a, b, _ = replicas_com_operacoes(s)
            ab, ba = copia(a), copia(b)
            ab.merge(b)
            ba.merge(a)
            self.assertEqual(ab.resumo(), ba.resumo())

    def test_associativo(self):
        for s in range(20):
            a, b, c = replicas_com_operacoes(s)
            esq = copia(a); esq.merge(b); esq.merge(c)       # (a ⊔ b) ⊔ c
            bc = copia(b); bc.merge(c)
            dir_ = copia(a); dir_.merge(bc)                   # a ⊔ (b ⊔ c)
            self.assertEqual(esq.resumo(), dir_.resumo())

    def test_idempotente(self):
        for s in range(20):
            a, b, _ = replicas_com_operacoes(s)
            uma = copia(a); uma.merge(b)
            duas = copia(uma); duas.merge(b); duas.merge(b)
            self.assertEqual(uma.resumo(), duas.resumo())

    def test_qualquer_ordem_de_entrega_converge(self):
        for s in range(10):
            reps = replicas_com_operacoes(s, n_replicas=4)
            resumos = set()
            for ordem in itertools.permutations(range(4)):
                alvo = EstadoReplica()
                for i in ordem:
                    alvo.merge(reps[i])
                resumos.add(alvo.resumo())
            self.assertEqual(len(resumos), 1)


class TestInventario(unittest.TestCase):
    def test_fefo_e_validade(self):
        e = EstadoReplica()
        inv = e.inventario
        inv.registrar_lote("velho", "SAB", validade=10)
        inv.registrar_lote("novo", "SAB", validade=300)
        inv.movimentar("p", "p", "velho", 5)
        inv.movimentar("p", "p", "novo", 20)
        self.assertEqual(inv.dispensar("p", "p", "SAB", 8, dia=1), 8)
        self.assertEqual(inv.saldo_lote("p", "velho"), 0)      # o que vence antes sai primeiro
        self.assertEqual(inv.saldo_lote("p", "novo"), 17)
        inv.movimentar("p", "p", "velho", 3)
        self.assertEqual(inv.saldo("p", "SAB", dia=11), 17)    # lote vencido não conta

    def test_dispensa_concorrente_e_detectada(self):
        a, b = EstadoReplica(), EstadoReplica()
        for r in (a, b):
            r.inventario.registrar_lote("L", "SAB", 100)
        a.inventario.movimentar("a", "p", "L", 10)
        b.merge(a)
        a.inventario.dispensar("a", "p", "SAB", 8, dia=0)      # dois aparelhos isolados
        b.inventario.dispensar("b", "p", "SAB", 8, dia=0)      # dispensam o mesmo estoque
        a.merge(b)
        self.assertEqual(a.inventario.saldo_lote("p", "L"), -6)
        self.assertEqual(a.inventario.saldos_negativos(), [("p", "L", -6)])


class TestRemessasEIdade(unittest.TestCase):
    def test_remessa_fica_em_transito_ate_confirmacao_chegar(self):
        polo, posto = EstadoReplica(), EstadoReplica()
        polo.remessas.adicionar("r1", {"origem": "polo", "destino": "posto", "soro": "SAB", "qtd": 30})
        self.assertEqual(polo.em_transito("polo", "posto", "SAB"), 30)
        posto.merge(polo)
        posto.recebimentos.adicionar("r1", {"remessa": "r1"})   # confirmada offline no posto
        self.assertEqual(polo.em_transito("polo", "posto"), 30)  # o polo ainda não sabe
        polo.merge(posto)
        self.assertEqual(polo.em_transito("polo", "posto"), 0)

    def test_mapa_maximo_fica_com_o_mais_recente(self):
        a, b = MapaMaximo({"x": 3.0, "y": 1.0}), MapaMaximo({"x": 2.0, "y": 5.0})
        a.merge(b)
        self.assertEqual(a.valores, {"x": 3.0, "y": 5.0})

    def test_ultimo_contato_nao_entra_no_resumo(self):
        a, b = EstadoReplica(), EstadoReplica()
        a.ultimo_contato.atualizar("x", 10.0)
        self.assertEqual(a.resumo(), b.resumo())


if __name__ == "__main__":
    unittest.main()
