"""Gera as figuras do README a partir do modelo da demo (dados sintéticos).

    python -m inadimplencia demo
    python scripts/gerar_figuras.py --modelo data/modelo --saida docs/img
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import matplotlib.dates

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from inadimplencia import risco  # noqa: E402

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e6e5e1"
# Paleta categórica em ordem fixa (validada para daltonismo nos pares adjacentes)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
CLASSES = ["Crônico", "Recorrente", "Novo", "Pontual"]
COR_CLASSE = dict(zip(CLASSES, SERIES))

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "axes.edgecolor": GRADE, "axes.labelcolor": TEXTO_2, "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "text.color": TEXTO, "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "legend.frameon": False,
})


def _reais(v: float, _=None) -> str:
    return f"R$ {v/1000:,.0f} mil".replace(",", ".")


def curva_reserva(saida: Path) -> None:
    dias = np.arange(0, 241)
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.plot(dias, 100 * risco.fator_reserva(dias), color=SERIES[0], lw=2,
            label="Reserva do modelo: (dias / 210)²")
    ax.step(dias, 100 * risco.provisao_2682(dias), where="pre", color=SERIES[1], lw=2,
            label="Provisão mínima da Res. CMN 2.682")
    for d in (90, 150, 180):
        m, r = 100 * risco.fator_reserva(d), 100 * risco.provisao_2682(d)[0]
        ax.plot([d, d], [m, r], color=TEXTO_2, lw=0.8, ls=":")
        for y, cor in ((m, SERIES[0]), (r, SERIES[1])):
            ax.scatter([d], [y], s=55, color=cor, edgecolor=SUPERFICIE, linewidth=2, zorder=3)
        ax.annotate(f"{d} dias: {m:.0f}% vs {r:.0f}%", (d, max(m, r)), xytext=(-8, 10),
                    textcoords="offset points", ha="right", fontsize=10, color=TEXTO_2)
    ax.set_xlim(0, 240)
    ax.set_ylim(0, 105)
    ax.set_xticks(range(0, 241, 30))
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_xlabel("Dias de atraso")
    ax.set_title("Reserva estimada vs. referência regulatória")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(saida / "curva_reserva.png", dpi=160)
    plt.close(fig)


def linha_do_tempo(modelo: Path, saida: Path, por_classe: int = 10) -> None:
    fcd = pd.read_parquet(modelo / "fato_cliente_dia.parquet")
    clientes = pd.read_parquet(modelo / "dim_cliente.parquet")
    datas = np.sort(fcd["data_snapshot"].unique())
    pos = {d: i for i, d in enumerate(datas)}

    fig, eixos = plt.subplots(len(CLASSES), 1, figsize=(10, 8.5), sharex=True,
                              gridspec_kw={"hspace": 0.55})
    rng = np.random.default_rng(3)
    for ax, classe in zip(eixos, CLASSES):
        docs = clientes.loc[clientes["classe"] == classe, "documento"].to_numpy()
        amostra = rng.choice(docs, size=min(por_classe, len(docs)), replace=False)
        primeira = fcd[fcd["documento"].isin(amostra)].groupby("documento")["data_snapshot"].min()
        amostra = primeira.sort_values().index.to_numpy()
        matriz = np.zeros((len(amostra), len(datas)))
        for i, doc in enumerate(amostra):
            for d in fcd.loc[fcd["documento"] == doc, "data_snapshot"]:
                matriz[i, pos[d]] = 1
        ax.imshow(matriz, aspect="auto", interpolation="nearest",
                  cmap=matplotlib.colors.ListedColormap([SUPERFICIE, SERIES[0]]), vmin=0, vmax=1)
        ax.set_yticks([])
        ax.grid(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_visible(False)
        total = int((clientes["classe"] == classe).sum())
        ax.set_title(f"{classe}  ·  {total} clientes (amostra de {len(amostra)})", fontsize=11)
    ticks = np.linspace(0, len(datas) - 1, 6).astype(int)
    eixos[-1].set_xticks(ticks)
    eixos[-1].set_xticklabels([pd.Timestamp(datas[t]).strftime("%d/%m") for t in ticks])
    eixos[-1].set_xlabel("Snapshot diário (cada linha é um cliente; azul = com saldo em atraso)")
    fig.suptitle("Linha do tempo da dívida por perfil de recorrência", x=0.01, ha="left",
                 fontsize=13, fontweight="bold")
    fig.subplots_adjust(left=0.03, right=0.98, top=0.9, bottom=0.08)
    fig.savefig(saida / "linha_do_tempo.png", dpi=160)
    plt.close(fig)


def saldo_por_classe(modelo: Path, saida: Path) -> None:
    fcd = pd.read_parquet(modelo / "fato_cliente_dia.parquet")
    classes = pd.read_parquet(modelo / "dim_cliente.parquet")[["documento", "classe"]]
    serie = (fcd.merge(classes, on="documento")
             .pivot_table(index="data_snapshot", columns="classe", values="saldo", aggfunc="sum")
             .reindex(columns=CLASSES).fillna(0))

    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.stackplot(serie.index, *[serie[c] for c in CLASSES], colors=SERIES, labels=CLASSES,
                 edgecolor=SUPERFICIE, linewidth=1.5)
    # rótulo direto na ponta de cada faixa que ainda tem saldo no fim
    base = 0.0
    for classe in CLASSES:
        valor = serie[classe].iloc[-1]
        if valor > serie.to_numpy().sum(axis=1).max() * 0.03:
            ax.annotate(classe, (serie.index[-1], base + valor / 2), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=10, color=TEXTO)
        base += valor
    ax.yaxis.set_major_formatter(_reais)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%Y"))
    ax.set_xlim(serie.index[0], serie.index[-1])
    ax.margins(x=0)
    ax.set_title("Saldo em atraso por perfil de recorrência (dados sintéticos)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4)
    fig.tight_layout()
    fig.subplots_adjust(right=0.88)
    fig.savefig(saida / "saldo_por_classe.png", dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", type=Path, default=Path("data/modelo"))
    ap.add_argument("--saida", type=Path, default=Path("docs/img"))
    args = ap.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    curva_reserva(args.saida)
    linha_do_tempo(args.modelo, args.saida)
    saldo_por_classe(args.modelo, args.saida)
    print(f"Figuras gravadas em {args.saida}/")


if __name__ == "__main__":
    main()
