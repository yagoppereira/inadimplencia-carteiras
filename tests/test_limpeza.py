from datetime import date

import pandas as pd
import pytest

from inadimplencia import limpeza


@pytest.mark.parametrize("bruto, esperado", [
    ("R$ 1.234,56", 1234.56),
    ("1234.56", 1234.56),
    ("R$ 980,00", 980.0),
    ("(10,50)", -10.5),
    ("", 0.0),
    (None, 0.0),
    (350, 350.0),
    ("texto", 0.0),
])
def test_converter_saldo(bruto, esperado):
    assert limpeza.converter_saldo(bruto) == pytest.approx(esperado)


@pytest.mark.parametrize("bruto, esperado", [
    ("12.345.678/0001-95", "12345678000195"),
    (12345678000195.0, "12345678000195"),
    ("345678000195", "00345678000195"),   # CNPJ que perdeu zeros à esquerda
    ("123.456.789-01", "12345678901"),
    ("00000000000000", ""),               # documento zerado (cliente do exterior)
    (None, ""),
])
def test_normalizar_documento(bruto, esperado):
    assert limpeza.normalizar_documento(bruto) == esperado


def test_raiz_agrupa_filiais_e_preserva_cpf():
    assert limpeza.raiz_documento("12345678000195") == "12345678"
    assert limpeza.raiz_documento("12345678901") == "12345678901"


def test_fatura_alfanumerica_nao_colide_com_numerica():
    assert limpeza.normalizar_fatura("NF-B1") == "NFB1"
    assert limpeza.normalizar_fatura("B1") != limpeza.normalizar_fatura("1")
    assert limpeza.normalizar_fatura("000123") == "123"
    assert limpeza.normalizar_fatura(123.0) == "123"


def test_mapear_colunas_por_palavra_chave():
    mapa = limpeza.mapear_colunas(["CNPJ/CPF", "Razão Social", "Saldo Devedor", "Vencimento", "Vendedor"])
    assert mapa["documento"] == "CNPJ/CPF"
    assert mapa["empresa"] == "Razão Social"
    assert mapa["saldo"] == "Saldo Devedor"


def test_mapear_colunas_exige_documento_e_saldo():
    with pytest.raises(ValueError):
        limpeza.mapear_colunas(["EMPRESA", "VENCIMENTO"])


def test_limpar_snapshot_descarta_total_e_soma_duplicatas():
    bruto = pd.DataFrame({
        "CNPJ": ["12345678000195", "12345678000195", "", "98765432000110", None],
        "EMPRESA": ["Transportes Ágil", "Transportes Ágil", "Sem doc", "Outra", "TOTAL GERAL"],
        "FATURA": ["100", "100", "101", "200", None],
        "VENCIMENTO": ["10/09/2026"] * 5,
        "SALDO": ["R$ 100,00", "R$ 50,00", "R$ 10,00", "R$ 0,00", "160,00"],
    })
    df = limpeza.limpar_snapshot(bruto, date(2026, 10, 1))
    assert len(df) == 1                       # sem doc, saldo zero e total saem
    linha = df.iloc[0]
    assert linha["saldo"] == pytest.approx(150.0)   # duplicata somada
    assert linha["empresa"] == "TRANSPORTES AGIL"
    assert linha["raiz"] == "12345678"
    assert linha["vendedor"] == "SEM VENDEDOR"
    assert list(df.columns) == limpeza.COLUNAS
