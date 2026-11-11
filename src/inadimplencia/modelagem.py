"""Modelo dimensional (estrela) e análise de recorrência da dívida.

Entrada: títulos limpos de todos os snapshots (`limpeza.consolidar`).

Saídas:
    dim_cliente           1 linha por cliente, com o perfil de recorrência
    dim_vendedor          1 linha por vendedor
    dim_produto           1 linha por produto (recorrente ou não)
    dim_data              1 linha por data de snapshot
    fato_titulo_snapshot  1 linha por título por dia (grão mais fino)
    fato_cliente_dia      1 linha por cliente por dia (linha do tempo)
    fato_episodio         1 linha por episódio de inadimplência

Episódio: período contínuo em que o cliente aparece com saldo em aberto.
Ausências de até `tolerancia_snapshots` não encerram o episódio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import risco
from .config import Parametros
from .limpeza import normalizar_texto

CLASSES = ("Crônico", "Recorrente", "Novo", "Pontual")


def _eh_recorrente(produto: str, params: Parametros) -> bool:
    p = normalizar_texto(produto)
    return any(p.startswith(r) for r in params.produtos_recorrentes)


def fato_titulo_snapshot(titulos: pd.DataFrame, params: Parametros) -> pd.DataFrame:
    df = titulos.copy()
    atraso = (df["data_snapshot"] - df["vencimento"]).dt.days
    df["dias_atraso"] = atraso.fillna(0).clip(lower=0).astype(int)
    df["faixa_atraso"] = df["dias_atraso"].map(risco.faixa_atraso)
    df["reserva"] = risco.reserva(
        df["saldo"], df["dias_atraso"], params.reserva_teto_dias, params.reserva_expoente
    ).round(2)
    df["mes_emissao"] = df["emissao"].dt.strftime("%Y-%m")
    return df


def fato_cliente_dia(fato_titulos: pd.DataFrame, params: Parametros) -> pd.DataFrame:
    df = fato_titulos.copy()
    recorrente = df["produto"].map(lambda p: _eh_recorrente(p, params))
    df["mes_recorrente"] = df["mes_emissao"].where(recorrente)
    agregado = (
        df.groupby(["data_snapshot", "documento"], as_index=False)
        .agg(
            vendedor=("vendedor", "first"),
            titulos=("fatura", "count"),
            saldo=("saldo", "sum"),
            reserva=("reserva", "sum"),
            dias_atraso_max=("dias_atraso", "max"),
            meses_em_aberto=("mes_recorrente", "nunique"),
        )
    )
    agregado["faixa_acumulo"] = agregado["meses_em_aberto"].map(risco.faixa_acumulo)
    return agregado


def episodios(cliente_dia: pd.DataFrame, params: Parametros) -> pd.DataFrame:
    """Quebra a presença de cada cliente em episódios contínuos."""
    datas = np.sort(cliente_dia["data_snapshot"].unique())
    if len(datas) == 0:
        return pd.DataFrame(columns=[
            "documento", "episodio", "inicio", "fim", "snapshots_presentes",
            "duracao_snapshots", "saldo_max", "em_aberto",
        ])
    indice = {d: i for i, d in enumerate(datas)}
    ultimo = len(datas) - 1
    passo_max = params.tolerancia_snapshots + 1

    linhas = []
    for documento, grupo in cliente_dia.sort_values("data_snapshot").groupby("documento"):
        pos = grupo["data_snapshot"].map(indice).to_numpy()
        saldos = grupo["saldo"].to_numpy()
        cortes = np.flatnonzero(np.diff(pos) > passo_max) + 1
        for n, (ini, fim) in enumerate(zip(np.r_[0, cortes], np.r_[cortes, len(pos)]), start=1):
            p_ini, p_fim = pos[ini], pos[fim - 1]
            linhas.append({
                "documento": documento,
                "episodio": n,
                "inicio": datas[p_ini],
                "fim": datas[p_fim],
                "snapshots_presentes": fim - ini,
                "duracao_snapshots": p_fim - p_ini + 1,
                "saldo_max": float(saldos[ini:fim].max()),
                "em_aberto": bool(ultimo - p_fim <= params.tolerancia_snapshots),
            })
    return pd.DataFrame(linhas)


def perfil_clientes(cliente_dia: pd.DataFrame, eps: pd.DataFrame, params: Parametros) -> pd.DataFrame:
    """Uma linha por cliente com presença, episódios e classe de recorrência."""
    datas = np.sort(cliente_dia["data_snapshot"].unique())
    indice = {d: i for i, d in enumerate(datas)}
    n_snap = len(datas)
    ultima_data = datas[-1] if n_snap else None

    base = (
        cliente_dia.sort_values("data_snapshot")
        .groupby("documento")
        .agg(
            primeira_aparicao=("data_snapshot", "min"),
            ultima_aparicao=("data_snapshot", "max"),
            snapshots_presentes=("data_snapshot", "count"),
            saldo_medio=("saldo", "mean"),
            saldo_max=("saldo", "max"),
            dias_atraso_max=("dias_atraso_max", "max"),
            vendedor_atual=("vendedor", "last"),
        )
    )
    atual = cliente_dia[cliente_dia["data_snapshot"] == ultima_data].set_index("documento")
    base["saldo_atual"] = atual["saldo"].reindex(base.index).fillna(0.0)
    base["meses_em_aberto_atual"] = atual["meses_em_aberto"].reindex(base.index).fillna(0).astype(int)
    base["n_episodios"] = eps.groupby("documento")["episodio"].max().reindex(base.index).fillna(0).astype(int)

    desde_primeira = n_snap - base["primeira_aparicao"].map(indice)
    base["presenca"] = (base["snapshots_presentes"] / desde_primeira).round(4)

    cronico = (base["presenca"] >= params.cronico_presenca_min) & (
        base["snapshots_presentes"] >= params.cronico_snapshots_min
    )
    novo = base["primeira_aparicao"].map(indice) >= n_snap - params.janela_novo_snapshots
    base["classe"] = np.select(
        [cronico, base["n_episodios"] >= 2, novo],
        ["Crônico", "Recorrente", "Novo"],
        default="Pontual",
    )
    base["em_aberto"] = base["saldo_atual"] > 0
    return base.reset_index()


def segmento(raiz: str, params: Parametros) -> str:
    return "Distribuidora" if raiz in params.raizes_distribuidoras else "Cliente Final"


def modelo_estrela(titulos: pd.DataFrame, params: Parametros | None = None) -> dict[str, pd.DataFrame]:
    params = params or Parametros()
    ft = fato_titulo_snapshot(titulos, params)
    fcd = fato_cliente_dia(ft, params)
    eps = episodios(fcd, params)
    perfil = perfil_clientes(fcd, eps, params)

    cadastro = (
        ft.sort_values("data_snapshot")
        .groupby("documento", as_index=False)
        .agg(raiz=("raiz", "last"), empresa=("empresa", "last"))
    )
    dim_cliente = cadastro.merge(perfil, on="documento", how="left")
    dim_cliente["segmento"] = dim_cliente["raiz"].map(lambda r: segmento(r, params))
    dim_cliente["distribuidora"] = dim_cliente["raiz"].map(params.raizes_distribuidoras).fillna("")

    dim_vendedor = (
        pd.DataFrame({"vendedor": sorted(ft["vendedor"].dropna().unique())})
        .assign(sem_dono=lambda d: d["vendedor"].isin(["SEM VENDEDOR", "NAO MAPEADO"]))
    )
    dim_produto = (
        pd.DataFrame({"produto": sorted(ft["produto"].dropna().unique())})
        .assign(recorrente=lambda d: d["produto"].map(lambda p: _eh_recorrente(p, params)))
    )
    datas = pd.Series(sorted(ft["data_snapshot"].unique()), name="data_snapshot")
    dim_data = pd.DataFrame({
        "data_snapshot": datas,
        "ano": datas.dt.year,
        "mes": datas.dt.month,
        "ano_mes": datas.dt.strftime("%Y-%m"),
        "semana_iso": datas.dt.isocalendar().week.astype(int).to_numpy(),
        "dia_semana": datas.dt.day_of_week,
        "ordem_snapshot": range(1, len(datas) + 1),
    })

    colunas_fato = [
        "data_snapshot", "documento", "vendedor", "produto", "fatura", "emissao",
        "vencimento", "mes_emissao", "dias_atraso", "faixa_atraso", "saldo", "reserva",
    ]
    return {
        "dim_cliente": dim_cliente,
        "dim_vendedor": dim_vendedor,
        "dim_produto": dim_produto,
        "dim_data": dim_data,
        "fato_titulo_snapshot": ft[colunas_fato],
        "fato_cliente_dia": fcd,
        "fato_episodio": eps,
    }
