# Apps Script: planilha central de inadimplência

Scripts do projeto Apps Script vinculado à planilha central. Para usar, cole cada arquivo no editor (Extensões → Apps Script) e preencha os IDs nos blocos `CONFIG_*`. Os valores do repositório são exemplos.

| Arquivo | O que faz |
|---|---|
| `SincronizarBases.gs` | Atualiza `Base_CIGAM` e `Base_Aparelhos` a partir do data warehouse (BigQuery) e `Base_Cidades` a partir da planilha de praças. A função `atualizarBasesEConsolidar()` roda a sequência toda. Nunca limpa uma base se a fonte voltar vazia |
| `ConsolidarBase.gs` | `consolidarBaseInteligente()`: cascata de atribuição que gera a `Base_Clientes` (ver [regras](../docs/regras_atribuicao.md)) |
| `DistribuirInadimplencia.gs` | `distribuirInadimplenciaPorVendedor()`: lê o arquivo do dia com leitura conferida, distribui os títulos para as planilhas dos vendedores, alimenta o Looker (`Dados_Looker`) e grava o histórico diário |
| `Relatorio.gs` | Layout e escrita da aba `Relatório`: saúde das bases, consolidação, maiores saldos sem dono e desempenho por vendedor |
| `Diagnostico.gs` | `diagnosticarSistema()`: confere abas, versões dos scripts, acessos, gatilhos, frescor e consistência, e grava o resultado na aba `Diagnóstico` |
| `AnonimizarDemo.gs` | Cria uma cópia anonimizada do `Dados_Looker` para demonstrações, ou anonimiza no lugar com backup e restauração |
| `Randomizador.gs` | Embaralha clientes, documentos, vendedores e valores de forma consistente entre abas em cópias de demonstração. Recusa rodar nos IDs de produção |
| `MenuAutomacoes.gs` | Menu "⚙️ Automações" na ordem do fluxo |

**Fluxo:** sincronizar as bases → consolidar a `Base_Clientes` → distribuir os títulos. Dois gatilhos diários rodam a sequência.

**Pré-requisitos:** os serviços avançados *BigQuery API* e *Drive API* habilitados no projeto.

Os scripts de validação da lista de vendedores, de criação das planilhas individuais e de atualização de layout fazem parte da operação, mas não estão neste repositório. O diagnóstico confere se eles existem.
