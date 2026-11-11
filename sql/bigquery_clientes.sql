-- Cadastro de clientes do ERP (camada bronze), uma linha por código.
-- A tabela bronze recebe uma versão nova do registro a cada carga: QUALIFY
-- mantém só a mais recente. Usada pela sincronização da Base_CIGAM.
SELECT
  TRIM(nomeCompleto)        AS nome,
  divisao.codigoDivisao     AS divisao,
  codigo,
  TRIM(fantasia)            AS fantasia,
  TRIM(cnpjCpf)             AS cnpj_cpf,
  ativo,
  TRIM(municipio)           AS municipio,
  UPPER(TRIM(uf))           AS uf
FROM `seu-projeto-gcp.bronze.erp__empresas`
WHERE divisao.codigoDivisao IN ('10', '11', '12', '90')   -- divisões que representam clientes
QUALIFY ROW_NUMBER() OVER (PARTITION BY codigo ORDER BY inserted_at DESC) = 1
ORDER BY nome;
