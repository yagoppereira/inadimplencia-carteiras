"""Gravação do modelo estrela e consultas SQL sobre ele (DuckDB)."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def salvar(tabelas: dict[str, pd.DataFrame], pasta: Path | str, formato: str = "parquet") -> list[Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for nome, df in tabelas.items():
        caminho = pasta / f"{nome}.{formato}"
        if formato == "parquet":
            df.to_parquet(caminho, index=False)
        else:
            df.to_csv(caminho, index=False, encoding="utf-8-sig")
        caminhos.append(caminho)
    return caminhos


def ler_consultas(arquivo_sql: Path | str) -> dict[str, str]:
    """Separa um arquivo .sql em consultas nomeadas por linhas `-- name: <nome>`."""
    texto = Path(arquivo_sql).read_text(encoding="utf-8")
    blocos = re.split(r"^--\s*name:\s*(\S+)\s*$", texto, flags=re.MULTILINE)
    return {nome: sql.strip().rstrip(";") for nome, sql in zip(blocos[1::2], blocos[2::2])}


def executar_consultas(pasta_modelo: Path | str, arquivo_sql: Path | str) -> dict[str, pd.DataFrame]:
    """Registra cada .parquet da pasta como view no DuckDB e roda as consultas nomeadas."""
    import duckdb

    con = duckdb.connect()
    for caminho in sorted(Path(pasta_modelo).glob("*.parquet")):
        con.execute(f"CREATE VIEW {caminho.stem} AS SELECT * FROM read_parquet('{caminho.as_posix()}')")
    return {nome: con.execute(sql).df() for nome, sql in ler_consultas(arquivo_sql).items()}
