# Data Warehouse da Campo Real Energia

Trabalho prático de Data Warehouse — Engenharia de Software, Centro Universitário Campo Real.

> **Pergunta da diretoria:** "Quanto a nossa geração vale, onde e quando ganhamos ou perdemos dinheiro, e podemos confiar nos números que nos mostram?"

Este repositório leva os dados do zero até o painel: **extrai** o PLD horário da CCEE e o clima do Open-Meteo pelas APIs, **avalia e trata a qualidade** de todas as tabelas, **modela** um star schema no PostgreSQL e entrega as **consultas e medidas** do painel no Power BI.

**Autor:** Gabriel Goes 

---

## Arquitetura

```
 Banco de origem (public)          APIs públicas
 usina, medicao_geracao...    CCEE (PLD)   Open-Meteo (clima)
            │                      │              │
            │                      ▼              ▼
            │                 raw.* (JSON exatamente como chegou + data/hora + URL)
            │                      │
            └──────────┬───────────┘
                       ▼
        Qualidade (Python): profiling + 47 regras nas 7 dimensões
        → qualidade.metrica / ocorrencia / quarentena / impacto_limpeza
                       ▼
             tratado.* (dado limpo, tipado, com chaves)
                       ▼
          dw_campo_real (star schema)  ──►  Power BI
```

Todas as execuções ficam registradas em `controle.log_execucao` (início, fim, linhas lidas, linhas gravadas, status e erro).

---

## Requisitos

- Python 3.10 ou superior
- PostgreSQL 13 ou superior (local ou [Neon](https://neon.tech)), com o script de origem da disciplina `campo_real_energia_postgres.sql` já executado
- Acesso à internet (APIs da CCEE e do Open-Meteo)
- Power BI Desktop (para o painel)

## Configuração

1. Instale as dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copie `.env.example` para `.env` e preencha a conexão. Use **uma** das formas:
   ```ini
   DATABASE_URL=postgresql://usuario:senha@host/banco?sslmode=require
   ```
   ou
   ```ini
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=campo_real_energia
   DB_USER=postgres
   DB_PASSWORD=sua_senha
   ```
   O `.env` está no `.gitignore`: **nenhuma credencial vai para o repositório**.
3. Os parâmetros que não são segredo ficam em `config/config.ini`: URLs das APIs, anos do PLD, variáveis de clima, timeout, número de tentativas, pausa entre requisições, limites do PLD da ANEEL e limiares das regras. Qualquer chave pode ser sobrescrita por uma variável de ambiente `SECAO_CHAVE` (ex.: `HTTP_TIMEOUT_SEGUNDOS=30`).

## Execução

Tudo de uma vez, na ordem certa:

```bash
python run_pipeline.py
```

Ou etapa por etapa (nesta ordem):

| # | Etapa | Comando | O que faz |
|---|---|---|---|
| 1 | estrutura | `python run_pipeline.py --etapas estrutura` | Cria os schemas `controle`, `raw`, `tratado`, `qualidade` e `dw_campo_real` |
| 2 | pld | `python run_pipeline.py --etapas pld` | Descobre os recursos do dataset `pld_horario`, pagina a API CKAN da CCEE (2025 e 2026), grava em `raw.ccee_pld_horario` e transforma em `tratado.pld_horario` |
| 3 | qualidade_origem | `python run_pipeline.py --etapas qualidade_origem` | Profiling, 39 regras sobre a origem e o PLD, limpeza, quarentena e cálculo do impacto antes × depois |
| 4 | clima | `python run_pipeline.py --etapas clima` | Busca o clima horário de 2025 no Open-Meteo nas coordenadas **já corrigidas** de cada usina |
| 5 | qualidade_clima | `python run_pipeline.py --etapas qualidade_clima` | 8 regras sobre o clima |
| 6 | dw | `python run_pipeline.py --etapas dw` | Cria e carrega o star schema (`sql/10_dw_ddl.sql` + `sql/11_dw_carga.sql`) |
| 7 | relatorio | `python run_pipeline.py --etapas relatorio` | Gera `docs/relatorio_qualidade.md` a partir das tabelas de qualidade |
| opcional | pld_simulado | `python run_pipeline.py --etapas pld_simulado` | **Plano B** (passo 4.9 do script da professora): grava um PLD simulado de 2025 **só nas horas sem PLD real**, marcado como `SIMULADO`. Quando a etapa `pld` voltar a funcionar, o dado real substitui o simulado. |

Opções: `--forcar` baixa de novo o que já está no raw; `-v` mostra logs detalhados.

O pipeline é **idempotente**: rodar de novo não duplica nada. Na segunda vez, as extrações encontram o dado no raw e terminam com status `CACHE`, sem chamar a API à toa.

### Sem instalar nada: Google Colab
Abra `notebooks/executar_no_colab.ipynb` no [Google Colab](https://colab.research.google.com), informe a string de conexão do Neon e execute todas as células.

## Tratamento de falhas na extração

| Situação | Comportamento |
|---|---|
| Tempo limite / conexão recusada | nova tentativa com espera exponencial (2 s, 4 s, 8 s…), até `tentativas` vezes |
| HTTP 429 (limite de requisições) | respeita o cabeçalho `Retry-After`; também há uma pausa fixa entre requisições |
| HTTP 5xx | nova tentativa com espera exponencial |
| Resposta vazia ou JSON inválido | nova tentativa; se o recurso não tiver registros, o log fica `SEM_DADOS` |
| Mudança de colunas | as colunas recebidas são comparadas com `colunas_esperadas`. Se faltar alguma, a execução falha com `ErroEsquema` e não grava lixo. Colunas novas são ignoradas e registradas como aviso. |
| Paginação | `limit`/`offset` ordenado por `_id`, até atingir o `total` informado pela API; página vazia encerra |
| Dado já baixado | retoma do `offset` igual ao que já existe no raw; se estiver completo, status `CACHE` |
| **Fonte fora do ar / bloqueada** | a execução fica com status `FALHA` e a mensagem de erro no log, mas **o pipeline não para**: a transformação e o DW seguem com o último dado válido do raw. Se a listagem do dataset falhar, usa os `resource_ids` do `config.ini`. Sem nenhum PLD, há o plano B `pld_simulado` (ver abaixo). |

Cada resposta da API é guardada **exatamente como chegou** (`raw.ccee_pld_horario.registro` e `raw.openmeteo_clima.resposta`, em JSONB), com `extraido_em`, `url_origem` e `id_execucao`.

## Ocorrência real: CCEE bloqueando a extração (HTTP 403)

Na execução de 12/11/2026, a API da CCEE respondeu **HTTP 403 — "Acesso bloqueado por não atender às políticas de segurança da CCEE"** para todas as requisições feitas pelo Python, tanto do Google Colab (IP do Google Cloud) quanto de uma rede residencial no Brasil. A mesma URL abre normalmente em um navegador.

Como o processo se comportou:
1. `extracao_pld` terminou com status **FALHA** e a mensagem do 403 em `controle.log_execucao`; não gravou nada no raw.
2. `transformacao_pld` ficou **SEM_DADOS** e o pipeline **seguiu** (qualidade, clima, DW, relatório).
3. A regra **MED-K04** apontou 100% das horas de geração sem PLD, e a carga do DW avisou que a receita ficaria nula.
4. Decisão do grupo: não contornar o bloqueio (ele é uma política de segurança da CCEE). Foi aberto chamado com o *error code* indicado na página, e a professora foi avisada.
5. Para não travar o painel, rodamos o **Plano B** da professora (`--etapas pld_simulado`). O PLD simulado fica identificado em `tratado.pld_horario.resource_id = 'SIMULADO'` e em `origem_pld` nos fatos do DW, e o painel mostra essa origem.

Para usar o dado real quando a CCEE liberar: `python run_pipeline.py --etapas pld,qualidade_origem,dw,relatorio`.

## Estrutura do repositório

```
├── run_pipeline.py              orquestrador (etapas)
├── config/
│   ├── config.ini               parâmetros (sem segredos)
│   └── referencia_municipios.csv  referência IBGE município → UF
├── src/
│   ├── config.py, db.py         configuração e acesso ao banco
│   ├── http_client.py           cliente HTTP com retry, backoff e rate limit
│   ├── log_execucao.py          registro em controle.log_execucao
│   ├── referencias.py           UF × submercado, limites das UFs, feriados nacionais
│   ├── extracao/                pld_ccee.py, clima_openmeteo.py, pld_simulado.py (plano B)
│   ├── qualidade/               verificacoes.py (funções reutilizáveis), regras.py (47 regras),
│   │                            limpeza.py, profiling.py, impacto.py, relatorio.py, executor.py
│   └── dw/carga.py
├── sql/
│   ├── 01_estrutura_etl.sql     schemas e tabelas de controle, raw, tratado e qualidade
│   ├── 10_dw_ddl.sql            DDL do star schema + procedure SCD + view
│   ├── 11_dw_carga.sql          carga do DW
│   ├── 20_consultas_negocio.sql as 7 perguntas da diretoria em SQL
│   └── 90_demo_scd2.sql         demonstração do SCD tipo 2 (com ROLLBACK)
├── docs/
│   ├── modelagem.md             matriz de barramento, grãos, SCD, granularidades, diagrama
│   ├── relatorio_qualidade.md   gerado pelo pipeline
│   └── img/star_schema.png
├── powerbi/
│   ├── guia_powerbi.md          conexão, relacionamentos, medidas DAX e páginas
│   └── painel_campo_real.pbix
└── notebooks/executar_no_colab.ipynb
```

## Entregáveis

| Entregável | Onde |
|---|---|
| Código de extração, carga e qualidade | `src/`, `run_pipeline.py` |
| Scripts SQL do DW | `sql/10_dw_ddl.sql`, `sql/11_dw_carga.sql` |
| Documento de modelagem | `docs/modelagem.md` |
| Relatório de qualidade | `docs/relatorio_qualidade.md` |
| Painel | `powerbi/painel_campo_real.pbix` |

## Regras do jogo atendidas

- As tabelas de origem (`public`) **nunca são alteradas**: a limpeza acontece em `tratado`.
- O painel lê **somente** `dw_campo_real`.
- O que já foi baixado não é baixado de novo (cache no raw).
- Os limites de requisição são respeitados (pausa entre chamadas e `Retry-After`).

## Fontes de dados e licenças

- **CCEE — Preço de Liquidação das Diferenças (PLD) horário**, conjunto `pld_horario`, [dadosabertos.ccee.org.br](https://dadosabertos.ccee.org.br/dataset/pld_horario). Licença **CC-BY 4.0**. Fonte: Câmara de Comercialização de Energia Elétrica (CCEE).
- **Open-Meteo — Historical Weather API**, [open-meteo.com](https://open-meteo.com/en/docs/historical-weather-api). Dados sob **CC-BY 4.0**, uso não comercial com atribuição: "Weather data by Open-Meteo.com".
- **Limites do PLD** (piso e teto horário) por ano: despachos da ANEEL (2025: R$ 58,60 e R$ 1.542,23; 2026: R$ 57,31 e R$ 1.611,04).
- **Dados operacionais** (usinas, medições, paradas): banco fictício da disciplina.
