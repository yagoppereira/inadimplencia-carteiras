import numpy as np
import pandas as pd
import pytest

from inadimplencia import risco


def test_curva_de_reserva():
    assert risco.fator_reserva(0) == 0
    assert risco.fator_reserva(105) == pytest.approx(0.25)   # metade do teto -> 25%
    assert risco.fator_reserva(210) == pytest.approx(1.0)
    assert risco.fator_reserva(400) == pytest.approx(1.0)    # teto
    assert risco.fator_reserva(-5) == 0                       # sem atraso


def test_curva_e_monotona():
    fatores = risco.fator_reserva(np.arange(0, 300))
    assert np.all(np.diff(fatores) >= 0)


@pytest.mark.parametrize("dias, esperado", [
    (0, 0.0), (14, 0.0), (15, 0.01), (30, 0.01), (31, 0.03), (90, 0.10),
    (91, 0.30), (180, 0.70), (181, 1.0),
])
def test_tabela_2682(dias, esperado):
    assert risco.provisao_2682(dias)[0] == pytest.approx(esperado)


def test_indice_de_risco():
    df = pd.DataFrame({"saldo": [100.0, 300.0], "dias": [210, 0]})
    df["reserva"] = risco.reserva(df["saldo"], df["dias"])
    assert risco.indice_risco(df) == pytest.approx(0.25)
    assert risco.indice_risco(df.iloc[0:0]) == 0.0


def test_faixas():
    assert risco.faixa_atraso(0) == "01. 1-30 dias"
    assert risco.faixa_atraso(31) == "02. 31-60 dias"
    assert risco.faixa_atraso(500) == "06. 180+ dias"
    assert risco.faixa_acumulo(0) == ""
    assert risco.faixa_acumulo(3) == "2 a 3 meses"
    assert risco.faixa_acumulo(13) == "Acima de 12 meses"
