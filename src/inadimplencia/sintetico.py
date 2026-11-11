"""Gerador de snapshots sintéticos, no mesmo formato da exportação real.

Nenhum dado real é usado: nomes, documentos e valores são gerados a partir de
uma semente. A ideia é que qualquer pessoa consiga rodar o pipeline inteiro.

Como funciona: cada cliente tem faturas mensais e um perfil de pagamento.
Uma fatura está em aberto no dia t se venceu antes de t e ainda não foi paga.
O perfil define quando cada fatura é paga:

    Pontual     um episódio curto de atraso no meio da série
    Recorrente  dois a quatro episódios separados por períodos em dia
    Crônico     paga sempre com 40 a 150 dias de atraso (sempre há algo em aberto)
    Novo        começa a atrasar nas últimas semanas
    Em dia      nunca atrasa (não aparece nos snapshots)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_PREFIXOS = ["TRANSPORTES", "LOGISTICA", "CONSTRUTORA", "MINERACAO", "AGRO", "COMERCIO DE COMBUSTIVEIS",
             "SANEAMENTO", "FROTA", "AUTO POSTO", "USINA", "TERRAPLENAGEM", "LOCADORA"]
_NOMES = ["AURORA", "BOA VISTA", "CAMPO BELO", "DELTA SUL", "ESTRELA", "FAROL", "GIRASSOL", "HORIZONTE",
          "IGUACU", "JACARANDA", "LITORAL", "MONTANHA", "NOVA ERA", "OURO VERDE", "PLANALTO", "RIO CLARO",
          "SERRA AZUL", "TROPICAL", "UNIAO", "VALE VERDE", "XAVANTES", "ZENITE", "PAMPA", "CERRADO"]
_SUFIXOS = ["LTDA", "LTDA", "LTDA", "S.A.", "EIRELI", "LTDA ME"]
VENDEDORES = ["ANA RIBEIRO", "BRUNO CASTRO", "CARLA MENDES", "DANIEL FARIAS", "ELISA MOURA",
              "FELIPE ARAUJO", "GABRIELA NUNES", "HENRIQUE LIMA", "ISABELA ROCHA", "JOAO PEDROSA",
              "KARINA SOUZA", "LUCAS TEIXEIRA"]
_PRODUTOS_RECORRENTES = [("Licenciamentos", 0.65), ("Aluguel", 0.35)]
_PRODUTOS_AVULSOS = ["Instalações", "Adesões", "Venda de equipamentos e periféricos"]
PERFIS = {"Em dia": 0.30, "Pontual": 0.28, "Recorrente": 0.18, "Crônico": 0.12, "Novo": 0.12}


def _digitos_cnpj(base12: str) -> str:
    """Calcula os dois dígitos verificadores de um CNPJ."""
    def dv(numeros: str, pesos: list[int]) -> str:
        resto = sum(int(n) * p for n, p in zip(numeros, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(base12, p1)
    d2 = dv(base12 + d1, [6] + p1)
    return base12 + d1 + d2


@dataclass
class _Fatura:
    numero: str
    emissao: date
    vencimento: date
    valor: float
    produto: str
    pagamento: date | None  # None = continua em aberto


@dataclass
class _Cliente:
    documento: str
    empresa: str
    vendedor: str
    perfil: str
    faturas: list[_Fatura]


def _gerar_clientes(n: int, dias: pd.DatetimeIndex, rng: np.random.Generator) -> list[_Cliente]:
    inicio, fim = dias[0].date(), dias[-1].date()
    meses = pd.date_range(inicio - timedelta(days=240), fim, freq="MS")
    distribuidoras = ["11111111", "22222222", "33333333"]
    clientes: list[_Cliente] = []
    raizes_usadas: list[str] = []
    seq_fatura = 100000

    for i in range(n):
        # ~8% filiais de um grupo já existente, ~2% distribuidoras, ~6% pessoa física
        sorteio = rng.random()
        if sorteio < 0.06:
            documento = "".join(rng.choice(list("0123456789"), 11))
        else:
            if sorteio < 0.08:
                raiz = distribuidoras[i % len(distribuidoras)]
            elif sorteio < 0.16 and raizes_usadas:
                raiz = raizes_usadas[rng.integers(len(raizes_usadas))]
            else:
                raiz = "".join(rng.choice(list("0123456789"), 8))
                raizes_usadas.append(raiz)
            filial = f"{rng.integers(1, 60):04d}"
            documento = _digitos_cnpj(raiz + filial)

        empresa = f"{rng.choice(_PREFIXOS)} {rng.choice(_NOMES)} {rng.choice(_SUFIXOS)}"
        vendedor = "SEM VENDEDOR" if rng.random() < 0.04 else VENDEDORES[rng.integers(len(VENDEDORES))]
        perfil = rng.choice(list(PERFIS), p=list(PERFIS.values()))
        produto = rng.choice([p for p, _ in _PRODUTOS_RECORRENTES], p=[w for _, w in _PRODUTOS_RECORRENTES])
        mensalidade = round(float(rng.lognormal(mean=6.3, sigma=0.7)), 2)  # mediana ~ R$ 545
        dia_venc = int(rng.choice([5, 10, 15, 20]))

        faturas = []
        for mes in meses:
            emissao = mes.date()
            vencimento = emissao.replace(day=dia_venc)
            seq_fatura += 1
            valor = round(mensalidade * float(rng.uniform(0.97, 1.03)), 2)
            faturas.append(_Fatura(str(seq_fatura), emissao, vencimento, valor, produto,
                                   pagamento=vencimento - timedelta(days=1)))
        if rng.random() < 0.3:  # cobrança avulsa (instalação, venda)
            base = faturas[rng.integers(len(faturas) - 6, len(faturas))]
            seq_fatura += 1
            faturas.append(_Fatura(f"A{seq_fatura}", base.emissao, base.vencimento,
                                   round(float(rng.lognormal(7.2, 0.8)), 2),
                                   str(rng.choice(_PRODUTOS_AVULSOS)), base.pagamento))

        _aplicar_perfil(perfil, faturas, dias, rng)
        clientes.append(_Cliente(documento, empresa, vendedor, perfil, faturas))
    return clientes


def _atrasar(faturas: list[_Fatura], de: date, ate: date, pagamento: date | None) -> None:
    """Faturas que vencem em [de, ate) só são pagas em `pagamento`."""
    for f in faturas:
        if de <= f.vencimento < ate:
            f.pagamento = pagamento


def _aplicar_perfil(perfil: str, faturas: list[_Fatura], dias: pd.DatetimeIndex,
                    rng: np.random.Generator) -> None:
    inicio, fim = dias[0].date(), dias[-1].date()
    n = len(dias)

    def dia(i: int) -> date:
        return dias[int(np.clip(i, 0, n - 1))].date()

    if perfil == "Em dia":
        return
    if perfil == "Crônico":
        for f in faturas:
            if f.vencimento >= inicio - timedelta(days=150):
                lag = int(rng.integers(40, 241))
                pago = f.vencimento + timedelta(days=lag)
                f.pagamento = None if pago > fim else pago
        return
    if perfil == "Novo":
        # passa a atrasar a partir da última fatura vencida: entra na série no último mês
        vencidas = sorted(f.vencimento for f in faturas if f.vencimento < fim - timedelta(days=2))
        _atrasar(faturas, vencidas[-1], fim + timedelta(days=1), None)
        return

    episodios = 1 if perfil == "Pontual" else int(rng.integers(2, 5))
    limite_inicio = n - 50 if perfil == "Pontual" else n // 4
    cursor = int(rng.integers(0, max(1, limite_inicio)))
    for _ in range(episodios):
        duracao = int(rng.integers(8, 35))  # em dias úteis, contados do vencimento
        de = dia(cursor) - timedelta(days=30)
        ate = dia(cursor)
        pagamento = dia(cursor + duracao)
        if cursor + duracao >= n - 12:  # não deixa o pontual virar "novo"
            break
        _atrasar(faturas, de, ate, pagamento)
        cursor += duracao + int(rng.integers(30, 60))  # volta a ficar em dia antes do próximo

    # metade dos recorrentes voltou a dever no último mês
    if perfil == "Recorrente" and rng.random() < 0.5:
        vencidas = sorted(f.vencimento for f in faturas if f.vencimento < fim - timedelta(days=2))
        if all(f.pagamento is not None and f.pagamento < vencidas[-1] for f in faturas
               if f.vencimento < vencidas[-1] - timedelta(days=20)):
            _atrasar(faturas, vencidas[-1], fim + timedelta(days=1), None)


def gerar_snapshots(
    pasta: str | Path,
    n_clientes: int = 400,
    fim: date = date(2026, 10, 30),
    n_dias_uteis: int = 130,
    falta_arquivo: float = 0.12,
    semente: int = 42,
) -> list[Path]:
    """Grava um CSV por dia em `pasta` e devolve os caminhos gerados."""
    rng = np.random.default_rng(semente)
    dias = pd.bdate_range(end=fim, periods=n_dias_uteis)
    clientes = _gerar_clientes(n_clientes, dias, rng)

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for t in dias:
        if rng.random() < falta_arquivo and t != dias[-1]:
            continue  # dia sem arquivo na pasta
        hoje = t.date()
        linhas = []
        for c in clientes:
            if c.perfil == "Crônico" and rng.random() < 0.01:
                continue  # linha faltando no arquivo do dia (ruído)
            for f in c.faturas:
                if f.vencimento < hoje and (f.pagamento is None or f.pagamento > hoje):
                    linhas.append({
                        "CNPJ": c.documento,
                        "EMPRESA": c.empresa,
                        "FATURA": f.numero,
                        "EMISSAO": f.emissao.strftime("%d/%m/%Y"),
                        "VENCIMENTO": f.vencimento.strftime("%d/%m/%Y"),
                        "SALDO": "R$ " + f"{f.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        "CONTA DESCRICAO": f.produto,
                        "VENDEDOR": c.vendedor,
                    })
        df = pd.DataFrame(linhas)
        total = sum(float(s[3:].replace(".", "").replace(",", ".")) for s in df["SALDO"]) if linhas else 0
        df.loc[len(df)] = {"EMPRESA": "TOTAL GERAL", "SALDO": f"{total:.2f}"}  # linha de totalização
        caminho = pasta / f"INADIMPLENCIA_{hoje:%Y-%m-%d}.csv"
        df.to_csv(caminho, sep=";", index=False, encoding="utf-8-sig")
        caminhos.append(caminho)

    gabarito = pd.DataFrame({"documento": [c.documento for c in clientes],
                             "perfil_gerado": [c.perfil for c in clientes]})
    gabarito.to_csv(pasta / "_gabarito_perfis.csv", index=False)
    return caminhos
