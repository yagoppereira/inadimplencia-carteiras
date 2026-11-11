# Modelo de dados (estrela)

Gerado por [`src/inadimplencia/modelagem.py`](../src/inadimplencia/modelagem.py) e gravado em Parquet. As análises de [`sql/analises.sql`](../sql/analises.sql) rodam sobre essas tabelas com DuckDB.

```mermaid
erDiagram
    dim_cliente ||--o{ fato_titulo_snapshot : documento
    dim_cliente ||--o{ fato_cliente_dia : documento
    dim_cliente ||--o{ fato_episodio : documento
    dim_vendedor ||--o{ fato_titulo_snapshot : vendedor
    dim_produto ||--o{ fato_titulo_snapshot : produto
    dim_data ||--o{ fato_titulo_snapshot : data_snapshot
    dim_data ||--o{ fato_cliente_dia : data_snapshot

    fato_titulo_snapshot {
        date data_snapshot
        string documento
        string vendedor
        string produto
        string fatura
        date vencimento
        int dias_atraso
        string faixa_atraso
        float saldo
        float reserva
    }
    fato_cliente_dia {
        date data_snapshot
        string documento
        int titulos
        float saldo
        float reserva
        int dias_atraso_max
        int meses_em_aberto
        string faixa_acumulo
    }
    fato_episodio {
        string documento
        int episodio
        date inicio
        date fim
        int snapshots_presentes
        float saldo_max
        bool em_aberto
    }
    dim_cliente {
        string documento PK
        string raiz
        string empresa
        string segmento
        string classe
        float presenca
        int n_episodios
        float saldo_atual
    }
    dim_vendedor {
        string vendedor PK
        bool sem_dono
    }
    dim_produto {
        string produto PK
        bool recorrente
    }
    dim_data {
        date data_snapshot PK
        string ano_mes
        int ordem_snapshot
    }
```

## Grãos

| Tabela | Grão | Para que serve |
|---|---|---|
| `fato_titulo_snapshot` | título × dia | Aging, carteira por vendedor, reserva |
| `fato_cliente_dia` | cliente × dia | Linha do tempo, evolução, acúmulo de mensalidades |
| `fato_episodio` | episódio de atraso | Duração e frequência dos atrasos |
| `dim_cliente` | cliente | Perfil de recorrência (classe) e segmento |

## Decisões

- **Chaves naturais.** O documento (CNPJ/CPF normalizado), o nome do vendedor e a data são estáveis e legíveis. Para uma ferramenta de BI com poucas tabelas, chaves substitutas não trariam ganho.
- **A raiz do CNPJ fica na dimensão** e agrupa filiais de um mesmo grupo. A atribuição de vendedor também usa a raiz.
- **Snapshot, não evento.** A fonte é uma foto diária do contas a receber, sem registro de pagamento. Por isso, o pagamento é inferido: o título sai do arquivo. A tolerância de 2 snapshots evita que um arquivo incompleto encerre um episódio por engano.
- **Meses em aberto** contam os meses de emissão distintos só dos produtos recorrentes (mensalidades). É o que a cobrança chama de "acúmulo".
