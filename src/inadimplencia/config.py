"""Parâmetros do pipeline.

Os valores padrão são os mesmos usados na operação real; todos podem ser
sobrescritos na linha de comando ou ao instanciar `Parametros`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Parametros:
    # Ausência tolerada (em snapshots) antes de considerar que a dívida foi
    # quitada. Evita quebrar um episódio por causa de um arquivo do dia que
    # veio incompleto ou de um pagamento que voltou.
    tolerancia_snapshots: int = 2

    # Crônico: cliente presente em pelo menos 80% dos snapshots, com um mínimo
    # de snapshots observados para a proporção ter algum significado.
    cronico_presenca_min: float = 0.80
    cronico_snapshots_min: int = 20

    # Novo: primeira aparição dentro dos últimos N snapshots (~ último mês útil).
    janela_novo_snapshots: int = 20

    # Curva de reserva: (min(dias, teto) / teto) ** expoente × saldo
    reserva_teto_dias: int = 210
    reserva_expoente: float = 2.0

    # Produtos de cobrança recorrente (mensalidades). Comparação pelo início
    # do texto, sem acento e em maiúsculas.
    produtos_recorrentes: tuple[str, ...] = ("LICENCIAMENTO", "ALUGUEL")

    # Raízes de CNPJ (8 dígitos) tratadas como distribuidoras. Fictícias.
    raizes_distribuidoras: dict[str, str] = field(
        default_factory=lambda: {
            "11111111": "Distribuidora A",
            "22222222": "Distribuidora B",
            "33333333": "Distribuidora C",
        }
    )


# Faixas de atraso (limite superior inclusivo em dias, rótulo)
FAIXAS_ATRASO: tuple[tuple[float, str], ...] = (
    (30, "01. 1-30 dias"),
    (60, "02. 31-60 dias"),
    (90, "03. 61-90 dias"),
    (120, "04. 91-120 dias"),
    (180, "05. 121-180 dias"),
    (float("inf"), "06. 180+ dias"),
)

# Faixas de acúmulo de mensalidades em aberto (limite superior, rótulo)
FAIXAS_ACUMULO: tuple[tuple[float, str], ...] = (
    (1, "1 mês"),
    (3, "2 a 3 meses"),
    (6, "4 a 6 meses"),
    (12, "7 a 12 meses"),
    (float("inf"), "Acima de 12 meses"),
)
