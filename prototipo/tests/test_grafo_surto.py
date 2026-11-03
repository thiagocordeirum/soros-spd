import unittest
from collections import Counter

from soro.grafo import GrafoMultimodal, cobertura, criticidade, rota
from soro.surto import c2


def grafo_linha():
    # C1 --2h-- P1 --1h-- P2 --5h-- C2
    g = GrafoMultimodal()
    for n in ("P1", "P2"):
        g.adicionar_local(n, "posto")
    for n in ("C1", "C2"):
        g.adicionar_local(n, "comunidade")
    g.adicionar_trecho("C1", "P1", 2, "voadeira")
    g.adicionar_trecho("P1", "P2", 1, "estrada")
    g.adicionar_trecho("P2", "C2", 5, "barco")
    return g


class TestGrafo(unittest.TestCase):
    def test_rota_para_posto_mais_proximo_com_soro(self):
        destino, horas, caminho = rota(grafo_linha(), "C1", {"P2"})
        self.assertEqual((destino, horas), ("P2", 3))
        self.assertEqual([loc for loc, _ in caminho], ["C1", "P1", "P2"])

    def test_cobertura(self):
        cob = cobertura(grafo_linha(), {"P1", "P2"})
        self.assertEqual(cob, {"C1": ("P1", 2), "C2": ("P2", 5)})

    def test_criticidade_serial_igual_paralela(self):
        g = grafo_linha()
        serial = criticidade(g, {"P1", "P2"}, limite_horas=5.5)
        paralela = criticidade(g, {"P1", "P2"}, limite_horas=5.5, trabalhadores=2)
        self.assertEqual(serial, paralela)
        self.assertEqual(serial, {"P1": 0, "P2": 1})  # sem P2, C2 fica a 6 h


class TestSurto(unittest.TestCase):
    def test_sem_alarme_sem_linha_de_base(self):
        self.assertFalse(c2(Counter({2: 10}), dia=2)[0])

    def test_alarme_quando_excede_limiar(self):
        historico = Counter({d: 1 for d in range(20)})
        historico[20] = 6
        alarme, observado, limiar = c2(historico, dia=20)
        self.assertTrue(alarme)
        self.assertEqual(observado, 6)
        self.assertAlmostEqual(limiar, 4.0)   # média 1 + 3 * sigma_min(1)
        historico[20] = 3
        self.assertFalse(c2(historico, dia=20)[0])


if __name__ == "__main__":
    unittest.main()
