"""Limpeza dos snapshots diários de inadimplência.

Cada snapshot é a exportação do contas a receber de um dia. Os arquivos
chegam com cabeçalhos que variam ("SALDO", "SALDO DEVEDOR", "VALOR"...),
valores no formato brasileiro ("R$ 1.234,56") e documentos sem zeros à
esquerda. Este módulo devolve um DataFrame com colunas e tipos fixos.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

import pandas as pd

COLUNAS = [
    "data_snapshot", "documento", "raiz", "empresa", "fatura",
    "emissao", "vencimento", "saldo", "produto", "vendedor",
]

# Palavras-chave procuradas no cabeçalho (já normalizado) para cada coluna.
# A ordem importa: a primeira coluna que casar é usada.
_MAPA_CABECALHO = {
    "documento": ("CNPJ", "CPF", "DOCUMENTO"),
    "empresa": ("EMPRESA", "RAZAO", "NOME", "CLIENTE"),
    "fatura": ("FATURA", "TITULO", "DOCUMENTO FISCAL", "NOTA"),
    "emissao": ("EMISSAO",),
    "vencimento": ("VENCIMENTO", "VENC"),
    "saldo": ("SALDO", "DEVEDOR", "VALOR"),
    "produto": ("CONTA DESCRICAO", "PRODUTO", "CONTA"),
    "vendedor": ("VENDEDOR", "CARTEIRA"),
}


def normalizar_texto(valor: object) -> str:
    """Maiúsculas, sem acento, sem espaço inseparável e com espaços simples."""
    if valor is None or (pd.api.types.is_scalar(valor) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFD", str(valor))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace(" ", " ").upper()
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_documento(valor: object) -> str:
    """Só dígitos; CPF com 11 e CNPJ com 14 posições. Vazio se não houver dígitos."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)  # 1234567000189.0 vindo do Excel
    digitos = re.sub(r"\D", "", str(valor))
    if not digitos or set(digitos) == {"0"}:
        return ""
    return digitos.zfill(11) if len(digitos) <= 11 else digitos.zfill(14)


def raiz_documento(documento: str) -> str:
    """Raiz de 8 dígitos para CNPJ (agrupa filiais); o próprio documento para CPF."""
    return documento[:8] if len(documento) == 14 else documento


def converter_saldo(valor: object) -> float:
    """Converte "R$ 1.234,56", "1234.56", "(10,00)" ou número em float."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return 0.0 if pd.isna(valor) else float(valor)
    texto = str(valor).strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if not texto:
        return 0.0
    negativo = (texto.startswith("(") and texto.endswith(")")) or texto.startswith("-")
    texto = texto.strip("()-")
    if "," in texto:  # formato brasileiro: ponto é milhar, vírgula é decimal
        texto = texto.replace(".", "").replace(",", ".")
    try:
        numero = float(texto)
    except ValueError:
        return 0.0
    return -numero if negativo else numero


def normalizar_fatura(valor: object) -> str:
    """Mantém letras e dígitos ("NF-B1" -> "NFB1"); remove zeros à esquerda só de números puros."""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = re.sub(r"[^0-9A-Z]", "", normalizar_texto(valor))
    if texto.isdigit():
        return texto.lstrip("0") or "0"
    return texto


def mapear_colunas(colunas: list[str]) -> dict[str, str]:
    """Devolve {coluna_padrao: coluna_original} procurando palavras-chave no cabeçalho."""
    normalizadas = {c: normalizar_texto(c) for c in colunas}
    mapa: dict[str, str] = {}
    for destino, chaves in _MAPA_CABECALHO.items():
        for chave in chaves:
            achada = next(
                (orig for orig, norm in normalizadas.items()
                 if chave in norm and orig not in mapa.values()),
                None,
            )
            if achada is not None:
                mapa[destino] = achada
                break
    faltando = {"documento", "saldo"} - mapa.keys()
    if faltando:
        raise ValueError(f"Colunas obrigatórias não encontradas: {sorted(faltando)}")
    return mapa


def _para_data(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, dayfirst=True, errors="coerce").dt.normalize()


def limpar_snapshot(bruto: pd.DataFrame, data_snapshot: date) -> pd.DataFrame:
    """Padroniza um snapshot bruto.

    Regras:
    - descarta linhas sem documento, com saldo <= 0 ou de totalização ("TOTAL");
    - um título (documento + fatura) aparece uma vez por dia: duplicatas somam o saldo.
    """
    mapa = mapear_colunas(list(bruto.columns))
    df = pd.DataFrame({destino: bruto[origem] for destino, origem in mapa.items()})
    for coluna in COLUNAS:
        if coluna not in df and coluna != "data_snapshot":
            df[coluna] = pd.NA

    df["documento"] = df["documento"].map(normalizar_documento)
    df["saldo"] = df["saldo"].map(converter_saldo)
    df["empresa"] = df["empresa"].map(normalizar_texto)
    df["fatura"] = df["fatura"].map(normalizar_fatura)
    df["produto"] = df["produto"].fillna("").astype(str).str.strip()
    df["vendedor"] = df["vendedor"].map(normalizar_texto).replace("", "SEM VENDEDOR")
    df["emissao"] = _para_data(df["emissao"])
    df["vencimento"] = _para_data(df["vencimento"])

    df = df[(df["documento"] != "") & (df["saldo"] > 0) & ~df["empresa"].str.contains("TOTAL")]
    df = df.assign(
        data_snapshot=pd.Timestamp(data_snapshot),
        raiz=df["documento"].map(raiz_documento),
    )

    chave = ["documento", "fatura"]
    agregado = (
        df.groupby(chave, as_index=False, dropna=False)
        .agg({
            "data_snapshot": "first", "raiz": "first", "empresa": "first",
            "emissao": "min", "vencimento": "min", "saldo": "sum",
            "produto": "first", "vendedor": "first",
        })
    )
    return agregado[COLUNAS].reset_index(drop=True)


def consolidar(snapshots: list[tuple[date, pd.DataFrame]]) -> pd.DataFrame:
    """Limpa e empilha vários snapshots, um por dia (o último arquivo do dia vence)."""
    por_dia: dict[date, pd.DataFrame] = {}
    for dia, bruto in snapshots:
        por_dia[dia] = bruto
    partes = [limpar_snapshot(bruto, dia) for dia, bruto in sorted(por_dia.items())]
    if not partes:
        return pd.DataFrame(columns=COLUNAS)
    return pd.concat(partes, ignore_index=True)
