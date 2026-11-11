"""Leitura dos snapshots: pasta local e, opcionalmente, Google Drive.

A data de cada snapshot vem do nome do arquivo. Formatos aceitos:
    2026-10-30   30-10-2026   30.10.2026   30_10_2026
"""
from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

import pandas as pd

_PADROES_DATA = (
    (re.compile(r"(\d{4})[-_.](\d{2})[-_.](\d{2})"), ("a", "m", "d")),
    (re.compile(r"(\d{2})[-_.](\d{2})[-_.](\d{4})"), ("d", "m", "a")),
)
EXTENSOES = {".csv", ".xlsx"}


def data_do_nome(nome: str) -> date | None:
    for padrao, ordem in _PADROES_DATA:
        m = padrao.search(nome)
        if m:
            partes = dict(zip(ordem, map(int, m.groups())))
            try:
                return date(partes["a"], partes["m"], partes["d"])
            except ValueError:
                return None
    return None


def ler_arquivo(caminho: Path | str, conteudo: bytes | None = None) -> pd.DataFrame:
    """Lê CSV (separador detectado) ou XLSX; tudo como texto para a limpeza decidir os tipos."""
    caminho = Path(caminho)
    origem = io.BytesIO(conteudo) if conteudo is not None else caminho
    if caminho.suffix.lower() == ".xlsx":
        return pd.read_excel(origem, dtype=str)  # requer openpyxl
    return pd.read_csv(origem, sep=None, engine="python", dtype=str, encoding="utf-8-sig")


def ler_pasta(pasta: Path | str) -> list[tuple[date, pd.DataFrame]]:
    """Lê todos os snapshots de uma pasta, ignorando arquivos sem data no nome."""
    snapshots = []
    for caminho in sorted(Path(pasta).iterdir()):
        if caminho.suffix.lower() not in EXTENSOES or caminho.name.startswith("_"):
            continue
        dia = data_do_nome(caminho.name)
        if dia is not None:
            snapshots.append((dia, ler_arquivo(caminho)))
    return snapshots


def baixar_pasta_drive(pasta_id: str, destino: Path | str, credenciais: str) -> list[Path]:
    """Baixa os snapshots de uma pasta do Drive com uma conta de serviço.

    Planilhas Google são exportadas como XLSX. Requer o extra `[drive]`
    (google-api-python-client, google-auth) e que a pasta esteja
    compartilhada com o e-mail da conta de serviço.
    """
    from google.oauth2 import service_account  # import tardio: dependência opcional
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    escopo = ["https://www.googleapis.com/auth/drive.readonly"]
    cred = service_account.Credentials.from_service_account_file(credenciais, scopes=escopo)
    drive = build("drive", "v3", credentials=cred, cache_discovery=False)

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    consulta = f"'{pasta_id}' in parents and trashed = false"
    gravados: list[Path] = []
    token = None
    while True:
        resposta = drive.files().list(
            q=consulta, fields="nextPageToken, files(id, name, mimeType)",
            pageToken=token, supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        for arq in resposta.get("files", []):
            if data_do_nome(arq["name"]) is None:
                continue
            if arq["mimeType"] == "application/vnd.google-apps.spreadsheet":
                pedido = drive.files().export_media(
                    fileId=arq["id"],
                    mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                nome = Path(arq["name"]).stem + ".xlsx"
            else:
                pedido = drive.files().get_media(fileId=arq["id"], supportsAllDrives=True)
                nome = arq["name"]
            buffer = io.BytesIO()
            baixador = MediaIoBaseDownload(buffer, pedido)
            concluido = False
            while not concluido:
                _, concluido = baixador.next_chunk()
            caminho = destino / nome
            caminho.write_bytes(buffer.getvalue())
            gravados.append(caminho)
        token = resposta.get("nextPageToken")
        if not token:
            return gravados
