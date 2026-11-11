-- Equipamentos por par (cliente onde está instalado, cliente que paga).
-- Base da regra de grandes contas: se a maior parte do que um pagante paga
-- está instalada em clientes da carteira de grandes contas, o pagante vai junto.
WITH emp AS (
  SELECT SAFE_CAST(codigo AS INT64) AS cod, codigo, TRIM(nomeCompleto) AS nome,
         LPAD(REGEXP_REPLACE(cnpjCpf, r'\D', ''), 14, '0') AS doc
  FROM `seu-projeto-gcp.bronze.erp__empresas`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY codigo ORDER BY inserted_at DESC) = 1
)
SELECT
  l.codigo  AS codigo_local,   l.doc  AS cnpj_local,   l.nome  AS nome_local,
  pg.codigo AS codigo_pagante, pg.doc AS cnpj_pagante, pg.nome AS nome_pagante,
  -- um equipamento pode aparecer em mais de uma linha (um por canal)
  COUNT(DISTINCT CONCAT(b.base, '-', CAST(b.equipamento_id AS STRING))) AS equipamentos
FROM `seu-projeto-gcp.gold.equipamentos_alocados` AS b
JOIN emp AS l  ON l.cod  = SAFE_CAST(b.cliente_erp_local   AS INT64)
JOIN emp AS pg ON pg.cod = SAFE_CAST(b.cliente_erp_pagante AS INT64)
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY cnpj_pagante, cnpj_local;
