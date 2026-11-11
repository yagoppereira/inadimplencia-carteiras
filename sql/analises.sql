-- Análises sobre o modelo estrela (DuckDB). Cada bloco começa com
-- "-- name: <nome>" e é executado por `python -m inadimplencia demo`.
--
-- Tabelas: dim_cliente, dim_vendedor, dim_produto, dim_data,
--          fato_titulo_snapshot, fato_cliente_dia, fato_episodio

-- name: carteira_por_vendedor
-- Posição do último snapshot: saldo, reserva e índice de risco por vendedor.
WITH ultimo AS (SELECT MAX(data_snapshot) AS d FROM dim_data)
SELECT
  f.vendedor,
  COUNT(DISTINCT f.documento)                       AS clientes,
  COUNT(*)                                          AS titulos,
  ROUND(SUM(f.saldo), 2)                            AS saldo,
  ROUND(SUM(f.reserva), 2)                          AS reserva,
  ROUND(100 * SUM(f.reserva) / SUM(f.saldo), 1)     AS indice_risco_pct,
  ROUND(100 * SUM(f.saldo) / SUM(SUM(f.saldo)) OVER (), 1) AS part_saldo_pct
FROM fato_titulo_snapshot f, ultimo
WHERE f.data_snapshot = ultimo.d
GROUP BY f.vendedor
ORDER BY saldo DESC;

-- name: aging_atual
-- Distribuição do saldo atual por faixa de atraso.
WITH ultimo AS (SELECT MAX(data_snapshot) AS d FROM dim_data)
SELECT
  f.faixa_atraso,
  COUNT(*)                                                  AS titulos,
  ROUND(SUM(f.saldo), 2)                                    AS saldo,
  ROUND(100 * SUM(f.saldo) / SUM(SUM(f.saldo)) OVER (), 1)  AS part_saldo_pct,
  ROUND(100 * SUM(f.reserva) / SUM(f.saldo), 1)             AS indice_risco_pct
FROM fato_titulo_snapshot f, ultimo
WHERE f.data_snapshot = ultimo.d
GROUP BY f.faixa_atraso
ORDER BY f.faixa_atraso;

-- name: recorrencia_por_classe
-- Quem está devendo agora, por perfil de recorrência.
SELECT
  c.classe,
  COUNT(*)                                       AS clientes,
  COUNT(*) FILTER (WHERE c.em_aberto)            AS em_aberto_hoje,
  ROUND(SUM(c.saldo_atual), 2)                   AS saldo_atual,
  ROUND(100 * SUM(c.saldo_atual) / SUM(SUM(c.saldo_atual)) OVER (), 1) AS part_saldo_pct,
  ROUND(AVG(c.n_episodios), 1)                   AS episodios_medios,
  ROUND(100 * AVG(c.presenca), 0)                AS presenca_media_pct
FROM dim_cliente c
GROUP BY c.classe
ORDER BY saldo_atual DESC;

-- name: evolucao_mensal
-- Média diária do saldo em atraso e do índice de risco, mês a mês.
SELECT
  d.ano_mes,
  COUNT(DISTINCT d.data_snapshot)                              AS snapshots,
  ROUND(SUM(f.saldo) / COUNT(DISTINCT d.data_snapshot), 2)     AS saldo_medio_dia,
  ROUND(COUNT(DISTINCT f.documento || CAST(f.data_snapshot AS VARCHAR))
        / COUNT(DISTINCT d.data_snapshot), 0)                  AS clientes_medio_dia,
  ROUND(100 * SUM(f.reserva) / SUM(f.saldo), 1)                AS indice_risco_pct
FROM fato_cliente_dia f
JOIN dim_data d USING (data_snapshot)
GROUP BY d.ano_mes
ORDER BY d.ano_mes;

-- name: duracao_dos_episodios
-- Quanto tempo um cliente leva para sair da inadimplência (episódios já encerrados).
SELECT
  CASE
    WHEN duracao_snapshots <= 5  THEN '01. até 5 snapshots'
    WHEN duracao_snapshots <= 15 THEN '02. 6 a 15'
    WHEN duracao_snapshots <= 30 THEN '03. 16 a 30'
    ELSE '04. mais de 30'
  END                                   AS duracao,
  COUNT(*)                              AS episodios,
  ROUND(MEDIAN(saldo_max), 2)           AS saldo_max_mediano
FROM fato_episodio
WHERE NOT em_aberto
GROUP BY 1
ORDER BY 1;

-- name: top_cronicos
-- Maiores saldos entre os clientes crônicos, com o acúmulo de mensalidades.
SELECT
  c.empresa,
  c.vendedor_atual                      AS vendedor,
  ROUND(c.saldo_atual, 2)               AS saldo_atual,
  c.meses_em_aberto_atual               AS meses_em_aberto,
  c.dias_atraso_max,
  ROUND(100 * c.presenca, 0)            AS presenca_pct
FROM dim_cliente c
WHERE c.classe = 'Crônico'
ORDER BY c.saldo_atual DESC
LIMIT 10;
