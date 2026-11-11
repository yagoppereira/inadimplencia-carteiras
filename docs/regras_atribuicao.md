# Regras de atribuição de clientes

Implementação: [`apps_script/ConsolidarBase.gs`](../apps_script/ConsolidarBase.gs), função `consolidarBaseInteligente()`.

## Entradas

| Aba | Origem | Conteúdo |
|---|---|---|
| `Base_CIGAM` | Data warehouse (ver [sql/bigquery_clientes.sql](../sql/bigquery_clientes.sql)) | Cadastro de clientes: documento, nome, cidade, UF |
| `Base_Comercial` | Histórico de vendas | Documento, razão social e vendedor de cada venda |
| `Base_Cidades` | Cópia automática da planilha de praças | Cidade + UF → vendedor regional |
| `Base_Aparelhos` | Data warehouse (ver [sql/bigquery_equipamentos.sql](../sql/bigquery_equipamentos.sql)) | Equipamentos por par (onde está instalado, quem paga) |
| `Insercoes_Manuais` | Mantida pela gestão | Documento → vendedor ou marcação especial |
| `Lista_Vendedores` | Mantida pela gestão | Vendedores ativos |

## Cascata

Cada cliente para na primeira regra que resolve. O nome da regra vai para a coluna `regra_atribuicao` da `Base_Clientes`.

1. **Inserção manual.** Primeiro o CNPJ exato, depois a raiz (8 dígitos), que vale para o grupo todo.
2. **Comercial pela raiz do CNPJ.** Usa o primeiro vendedor que vendeu para qualquer CNPJ da mesma raiz.
3. **Comercial pela razão social.** Primeiro a exata, depois a parcial. A comparação usa o nome limpo: sem sufixos societários (LTDA, S/A, EIRELI...), sem acento e sem a cidade anexada ao nome. Nomes com menos de 5 letras ficam fora da busca parcial, para evitar falsos positivos.
4. **Praça.** A chave é `CIDADE_UF`, sem acento e em maiúsculas, também testada sem espaços. Grafias diferentes entre o ERP e a planilha de praças são resolvidas por uma tabela de apelidos.
5. **Retenção.** Se o vendedor encontrado nas regras 2 e 3 está inativo e nenhuma regra seguinte resolveu, o cliente fica com ele, marcado como retido, para continuar visível até ser redistribuído.
6. **Grande conta** (segunda passada, depois da cascata). Para cada cliente que **paga** equipamentos, calcula quanto dos equipamentos que ele paga está instalado em clientes da carteira de grandes contas. Se for ≥ 50%, o pagante vai para essa carteira. As inserções manuais, a marcação `REGIONAL` e a carteira de parcerias sempre prevalecem.

Quem não cai em nenhuma regra fica como `NÃO MAPEADO` e aparece nominalmente no diagnóstico.

## Controles manuais

| Caso | Como usar | Efeito |
|---|---|---|
| Vendedor de **parcerias** (só recebe o que for inserido à mão) | Nome em `CONFIG_ATRIBUICAO.vendedoresSomenteManual` | As vendas e praças dele são ignoradas e o cliente segue para a próxima regra, normalmente o vendedor regional. A regra fica marcada com " · parceria" |
| Cliente que deve ir para o **vendedor regional** | Na `Insercoes_Manuais`: documento e `REGIONAL` | Ignora o histórico comercial e atribui pela praça. A regra fica "4. Praça (Regional por inserção)" |
| Cliente que deve **sair das grandes contas** | Na `Insercoes_Manuais`: documento e `SEM GRANDE CONTA` | Segue a cascata normal, só não é puxado pela regra 6. A regra ganha " · sem grande conta" |
| Cidade escrita de outro jeito | `CONFIG_ATRIBUICAO.apelidosCidade` | `"MOJI MIRIM_SP" → "MOGI MIRIM_SP"` |

## Auditoria

- A `Base_Clientes` guarda a regra de cada cliente.
- A aba `Relatório` mostra a contagem por regra, a cobertura, os maiores saldos sem dono e o desempenho por vendedor.
- A função `diagnosticarSistema()` confere as versões dos scripts, os acessos, os gatilhos, o frescor de cada base e os clientes sem vendedor, e lista o que precisa de atenção.
