# Camada semântica: métricas do dashboard de gestão

Definições únicas usadas no Looker Studio, em sintaxe de campo calculado. A mesma lógica está em Python ([`risco.py`](../src/inadimplencia/risco.py)) e em SQL ([`analises.sql`](../sql/analises.sql)).

## Medidas

| Métrica | Definição | Observação |
|---|---|---|
| Saldo | `SUM(Saldo)` | Moeda R$ |
| Reserva Estimada (R$) | `Saldo * POWER(CASE WHEN Dias de Atraso >= 210 THEN 1 ELSE Dias de Atraso / 210 END, 2)` | Por linha. No gráfico, `SUM` |
| Índice de Risco (%) | `SUM(Reserva Estimada (R$)) / SUM(Saldo)` | Razão de somas, nunca média de razões |
| Índice de Risco – Cliente Final | `SUM(CASE WHEN Segmento = "Cliente Final" THEN Reserva Estimada (R$) ELSE 0 END) / SUM(CASE WHEN Segmento = "Cliente Final" THEN Saldo ELSE 0 END)` | Exclui distribuidoras |
| Saldo por Cliente | `SUM(Saldo) / COUNT_DISTINCT(CNPJ)` | Substitui o "ticket médio" por título |
| Meses em Aberto | Coluna gravada pela distribuição | Valor do cliente, repetido nas linhas dele: use `MAX`, nunca `SUM` |
| Mensalidade Média (R$) | `SUM(CASE WHEN Produto (Resumido) IN ("Licenciamentos", "Aluguel") THEN Saldo ELSE 0 END) / MAX(Meses em Aberto)` | Por cliente |

## Dimensões

| Dimensão | Valores | Ordenação |
|---|---|---|
| Faixa de Atraso | 1-30 · 31-60 · 61-90 · 91-120 · 121-180 · 180+ dias | Prefixo numérico no rótulo ("01. 1-30 dias") |
| Faixa de Acúmulo | 1 mês · 2 a 3 · 4 a 6 · 7 a 12 · acima de 12 meses | Campo `Ordem Acúmulo` (CASE → 1..6) |
| Segmento | Distribuidora · Cliente Final | Pela raiz do CNPJ |
| Produto (Resumido) | Agrupamento das contas do ERP | — |

## Regras de visualização adotadas

- **Uma métrica por eixo.** Um gráfico antigo cruzava R$ com quantidade de meses em dois eixos. Ele virou dois componentes: barras de clientes por faixa de acúmulo e uma tabela com os maiores acúmulos.
- **Tendência em gráficos separados:** saldo total, índice de risco (recalculado como razão de somas) e barras 100% por faixa de atraso, que mostram o envelhecimento da carteira.
- **O mapa colore pelo índice de risco**, e o saldo e a reserva ficam na dica de ferramenta.
- **Filtros de vendedor e segmento** em uma linha acima dos gráficos.
