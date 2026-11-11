"""Teste de ponta a ponta com dados sintéticos: gera, lê, modela e consulta."""
from pathlib import Path

import pandas as pd
import pytest

from inadimplencia import fontes, limpeza, modelagem, saida, sintetico
from inadimplencia.config import Parametros

SQL = Path(__file__).resolve().parents[1] / "sql" / "analises.sql"


@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("dados")
    sintetico.gerar_snapshots(pasta / "brutos", n_clientes=150, n_dias_uteis=90, semente=7)
    snapshots = fontes.ler_pasta(pasta / "brutos")
    tabelas = modelagem.modelo_estrela(limpeza.consolidar(snapshots), Parametros())
    saida.salvar(tabelas, pasta / "modelo")
    return pasta, snapshots, tabelas


def test_data_vem_do_nome_do_arquivo():
    assert str(fontes.data_do_nome("INADIMPLENCIA_2026-10-30.csv")) == "2026-10-30"
    assert str(fontes.data_do_nome("Inadimp 30.10.2026.xlsx")) == "2026-10-30"
    assert fontes.data_do_nome("sem data.csv") is None


def test_saldo_lido_bate_com_a_linha_de_total(modelo):
    pasta, snapshots, _ = modelo
    dia, bruto = snapshots[-1]
    total_arquivo = limpeza.converter_saldo(bruto.loc[bruto["EMPRESA"] == "TOTAL GERAL", "SALDO"].iloc[0])
    limpo = limpeza.limpar_snapshot(bruto, dia)
    assert limpo["saldo"].sum() == pytest.approx(total_arquivo, abs=0.05)


def test_chaves_do_modelo_estrela(modelo):
    _, _, t = modelo
    fato, dim_cliente = t["fato_titulo_snapshot"], t["dim_cliente"]
    assert dim_cliente["documento"].is_unique
    assert set(fato["documento"]) <= set(dim_cliente["documento"])
    assert set(fato["data_snapshot"]) <= set(t["dim_data"]["data_snapshot"])
    assert set(fato["vendedor"]) <= set(t["dim_vendedor"]["vendedor"])
    assert not fato.duplicated(["data_snapshot", "documento", "fatura"]).any()


def test_classificacao_recupera_os_perfis_gerados(modelo):
    pasta, _, t = modelo
    gabarito = pd.read_csv(pasta / "brutos" / "_gabarito_perfis.csv", dtype=str)
    junto = t["dim_cliente"].merge(gabarito, on="documento")
    assert (junto["classe"] == junto["perfil_gerado"]).mean() >= 0.9
    assert set(junto.loc[junto["perfil_gerado"] == "Crônico", "classe"]) == {"Crônico"}


def test_consultas_sql_rodam(modelo):
    pasta, _, t = modelo
    resultados = saida.executar_consultas(pasta / "modelo", SQL)
    assert {"carteira_por_vendedor", "aging_atual", "recorrencia_por_classe"} <= resultados.keys()
    ultimo = t["fato_titulo_snapshot"]["data_snapshot"].max()
    saldo_atual = t["fato_titulo_snapshot"].query("data_snapshot == @ultimo")["saldo"].sum()
    assert resultados["carteira_por_vendedor"]["saldo"].sum() == pytest.approx(saldo_atual, rel=1e-6)
    assert resultados["aging_atual"]["part_saldo_pct"].sum() == pytest.approx(100, abs=0.5)
