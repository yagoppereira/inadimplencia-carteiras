import pandas as pd
import pytest

from inadimplencia import modelagem
from inadimplencia.config import Parametros

DATAS = pd.bdate_range("2026-01-05", periods=40)


def _cliente_dia(presencas: dict[str, list[int]]) -> pd.DataFrame:
    """Monta fato_cliente_dia a partir de {documento: índices dos snapshots presentes}."""
    linhas = [
        {"data_snapshot": DATAS[i], "documento": doc, "vendedor": "V", "titulos": 1,
         "saldo": 100.0 + i, "reserva": 1.0, "dias_atraso_max": 10, "meses_em_aberto": 1}
        for doc, indices in presencas.items() for i in indices
    ]
    # garante que a série tenha todas as datas, mesmo que nenhum cliente teste use a última
    linhas += [{"data_snapshot": d, "documento": "ANCORA", "vendedor": "V", "titulos": 1,
                "saldo": 1.0, "reserva": 0.0, "dias_atraso_max": 1, "meses_em_aberto": 0}
               for d in DATAS]
    return pd.DataFrame(linhas)


def test_lacuna_dentro_da_tolerancia_nao_quebra_episodio():
    fcd = _cliente_dia({"A": [0, 1, 2, 5, 6]})          # pula 2 snapshots (3 e 4)
    eps = modelagem.episodios(fcd, Parametros(tolerancia_snapshots=2))
    a = eps[eps["documento"] == "A"]
    assert len(a) == 1
    assert a.iloc[0]["snapshots_presentes"] == 5
    assert a.iloc[0]["duracao_snapshots"] == 7


def test_lacuna_acima_da_tolerancia_abre_novo_episodio():
    fcd = _cliente_dia({"A": [0, 1, 2, 6, 7]})          # pula 3 snapshots
    eps = modelagem.episodios(fcd, Parametros(tolerancia_snapshots=2))
    a = eps[eps["documento"] == "A"].sort_values("episodio")
    assert list(a["episodio"]) == [1, 2]
    assert a.iloc[1]["inicio"] == DATAS[6]
    assert not a.iloc[0]["em_aberto"]


def test_episodio_em_aberto_considera_tolerancia_no_fim():
    fcd = _cliente_dia({"A": [30, 31, 37]})             # sumiu nos 2 últimos snapshots
    eps = modelagem.episodios(fcd, Parametros(tolerancia_snapshots=2))
    assert eps[eps["documento"] == "A"].iloc[-1]["em_aberto"]


@pytest.mark.parametrize("presenca, classe", [
    (list(range(0, 40)), "Crônico"),
    ([0, 1, 2, 3, 15, 16, 17], "Recorrente"),
    (list(range(5, 15)), "Pontual"),
    ([35, 36, 37, 38, 39], "Novo"),
    (list(range(0, 15)), "Pontual"),                    # 15 snapshots: abaixo do mínimo de crônico
])
def test_classificacao(presenca, classe):
    params = Parametros(janela_novo_snapshots=10)
    fcd = _cliente_dia({"A": presenca})
    eps = modelagem.episodios(fcd, params)
    perfil = modelagem.perfil_clientes(fcd, eps, params).set_index("documento")
    assert perfil.loc["A", "classe"] == classe


def test_crônico_exige_presenca_minima():
    presentes = [i for i in range(40) if i % 3 != 0]     # 66% de presença, lacunas de 1
    params = Parametros()
    fcd = _cliente_dia({"A": presentes})
    eps = modelagem.episodios(fcd, params)
    perfil = modelagem.perfil_clientes(fcd, eps, params).set_index("documento")
    assert perfil.loc["A", "presenca"] < params.cronico_presenca_min
    assert perfil.loc["A", "classe"] != "Crônico"
