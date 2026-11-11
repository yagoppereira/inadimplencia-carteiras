"""Linha de comando.

    python -m inadimplencia demo                      # gera dados sintéticos e roda tudo
    python -m inadimplencia processar --entrada PASTA # snapshots reais em uma pasta
    python -m inadimplencia baixar --pasta-id ID --credenciais sa.json --destino PASTA
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import fontes, limpeza, modelagem, saida, sintetico
from .config import Parametros

RAIZ = Path(__file__).resolve().parents[2]
SQL_ANALISES = RAIZ / "sql" / "analises.sql"


def processar(entrada: Path, destino: Path, params: Parametros, consultas: bool = True) -> dict:
    snapshots = fontes.ler_pasta(entrada)
    if not snapshots:
        raise SystemExit(f"Nenhum snapshot com data no nome em {entrada}")
    titulos = limpeza.consolidar(snapshots)
    tabelas = modelagem.modelo_estrela(titulos, params)
    saida.salvar(tabelas, destino)

    clientes = tabelas["dim_cliente"]
    print(f"\n{len(snapshots)} snapshots · {len(titulos):,} títulos-dia · {len(clientes):,} clientes")
    print(f"Modelo estrela gravado em {destino}/")
    print("\nClientes por classe de recorrência:")
    print(clientes["classe"].value_counts().reindex(modelagem.CLASSES, fill_value=0).to_string())

    if consultas and SQL_ANALISES.exists():
        pd.set_option("display.width", 140)
        for nome, df in saida.executar_consultas(destino, SQL_ANALISES).items():
            print(f"\n== {nome} ==")
            print(df.head(12).to_string(index=False))
    return tabelas


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="inadimplencia", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)

    demo = sub.add_parser("demo", help="gera snapshots sintéticos e processa")
    demo.add_argument("--clientes", type=int, default=400)
    demo.add_argument("--semente", type=int, default=42)
    demo.add_argument("--pasta", type=Path, default=Path("data"))

    proc = sub.add_parser("processar", help="processa uma pasta de snapshots")
    proc.add_argument("--entrada", type=Path, required=True)
    proc.add_argument("--destino", type=Path, default=Path("data/modelo"))
    proc.add_argument("--tolerancia", type=int, default=Parametros.tolerancia_snapshots)
    proc.add_argument("--sem-consultas", action="store_true")

    baixar = sub.add_parser("baixar", help="baixa snapshots de uma pasta do Google Drive")
    baixar.add_argument("--pasta-id", required=True)
    baixar.add_argument("--credenciais", required=True, help="JSON da conta de serviço")
    baixar.add_argument("--destino", type=Path, default=Path("data/snapshots"))

    args = ap.parse_args(argv)
    if args.comando == "demo":
        brutos = args.pasta / "sintetico"
        arquivos = sintetico.gerar_snapshots(brutos, n_clientes=args.clientes, semente=args.semente)
        print(f"{len(arquivos)} snapshots sintéticos gravados em {brutos}/")
        processar(brutos, args.pasta / "modelo", Parametros())
    elif args.comando == "processar":
        processar(args.entrada, args.destino, Parametros(tolerancia_snapshots=args.tolerancia),
                  consultas=not args.sem_consultas)
    elif args.comando == "baixar":
        arquivos = fontes.baixar_pasta_drive(args.pasta_id, args.destino, args.credenciais)
        print(f"{len(arquivos)} arquivos baixados em {args.destino}/")
