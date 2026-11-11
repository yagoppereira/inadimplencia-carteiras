"""Modelo de risco: reserva estimada por título e índice de risco da carteira.

A reserva cresce de forma quadrática com os dias de atraso até um teto
(210 dias por padrão), quando o título é considerado 100% em risco:

    reserva = (min(dias, teto) / teto) ** expoente × saldo
    índice de risco = Σ reserva / Σ saldo

A curva é contínua (não dá saltos de um dia para o outro) e fica abaixo da
tabela da Resolução CMN 2.682 nas faixas iniciais, onde boa parte dos
atrasos de mensalidade é operacional, e converge para 100% antes dela.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FAIXAS_ACUMULO, FAIXAS_ATRASO

# Res. CMN 2.682/1999: provisão mínima por faixa de atraso (limite superior em dias, %)
TABELA_2682: tuple[tuple[float, float], ...] = (
    (14, 0.0), (30, 0.01), (60, 0.03), (90, 0.10), (120, 0.30),
    (150, 0.50), (180, 0.70), (float("inf"), 1.00),
)


def fator_reserva(dias, teto: int = 210, expoente: float = 2.0):
    """Fração do saldo reservada para um atraso de `dias` (escalar ou array)."""
    d = np.clip(np.asarray(dias, dtype=float), 0, teto)
    return (d / teto) ** expoente


def reserva(saldo, dias, teto: int = 210, expoente: float = 2.0):
    return np.asarray(saldo, dtype=float) * fator_reserva(dias, teto, expoente)


def provisao_2682(dias) -> np.ndarray:
    """Percentual mínimo de provisão pela Res. CMN 2.682 (escalar ou array)."""
    d = np.atleast_1d(np.asarray(dias, dtype=float))
    limites = np.array([lim for lim, _ in TABELA_2682])
    percentuais = np.array([p for _, p in TABELA_2682])
    return percentuais[np.searchsorted(limites, d, side="left")]


def indice_risco(df: pd.DataFrame, col_saldo: str = "saldo", col_reserva: str = "reserva") -> float:
    total = df[col_saldo].sum()
    return float(df[col_reserva].sum() / total) if total else 0.0


def _faixa(valor: float, faixas) -> str:
    for limite, rotulo in faixas:
        if valor <= limite:
            return rotulo
    return faixas[-1][1]


def faixa_atraso(dias: float) -> str:
    return _faixa(max(dias, 1), FAIXAS_ATRASO)


def faixa_acumulo(meses: float) -> str:
    return "" if meses <= 0 else _faixa(meses, FAIXAS_ACUMULO)
