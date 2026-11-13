CREATE SCHEMA IF NOT EXISTS controle;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS tratado;
CREATE SCHEMA IF NOT EXISTS qualidade;

CREATE TABLE IF NOT EXISTS controle.log_execucao (
    id_execucao      SERIAL PRIMARY KEY,
    processo         VARCHAR(60)  NOT NULL,
    fonte            VARCHAR(60)  NOT NULL,
    parametros       JSONB,
    inicio           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fim              TIMESTAMPTZ,
    linhas_lidas     INTEGER      NOT NULL DEFAULT 0,
    linhas_gravadas  INTEGER      NOT NULL DEFAULT 0,
    status           VARCHAR(20)  NOT NULL CHECK (status IN ('EXECUTANDO','SUCESSO','SEM_DADOS','PARCIAL','CACHE','FALHA')),
    mensagem_erro    TEXT
);
COMMENT ON TABLE controle.log_execucao IS 'Uma linha por execucao de cada processo (extracao, transformacao, qualidade, carga do DW).';

CREATE TABLE IF NOT EXISTS raw.ccee_pld_horario (
    id_raw        BIGSERIAL PRIMARY KEY,
    resource_id   VARCHAR(64)  NOT NULL,
    ano_recurso   INTEGER      NOT NULL,
    id_registro   BIGINT       NOT NULL,
    registro      JSONB        NOT NULL,
    url_origem    TEXT         NOT NULL,
    extraido_em   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    id_execucao   INTEGER      REFERENCES controle.log_execucao(id_execucao),
    UNIQUE (resource_id, id_registro)
);
COMMENT ON TABLE raw.ccee_pld_horario IS 'Camada raw do PLD horario da CCEE: cada registro exatamente como veio da API CKAN (JSON), com origem e momento da extracao. Grao: 1 registro da API.';

CREATE TABLE IF NOT EXISTS raw.openmeteo_clima (
    id_raw        BIGSERIAL PRIMARY KEY,
    cod_usina     VARCHAR(12)   NOT NULL,
    latitude      NUMERIC(9,6)  NOT NULL,
    longitude     NUMERIC(9,6)  NOT NULL,
    data_inicio   DATE          NOT NULL,
    data_fim      DATE          NOT NULL,
    parametros    JSONB         NOT NULL,
    resposta      JSONB         NOT NULL,
    url_origem    TEXT          NOT NULL,
    extraido_em   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    id_execucao   INTEGER       REFERENCES controle.log_execucao(id_execucao),
    UNIQUE (cod_usina, latitude, longitude, data_inicio, data_fim)
);
COMMENT ON TABLE raw.openmeteo_clima IS 'Camada raw do Open-Meteo: resposta JSON completa de cada requisicao (1 ponto = coordenadas de 1 usina, 1 periodo).';

CREATE TABLE IF NOT EXISTS tratado.pld_horario (
    cod_submercado           CHAR(2)        NOT NULL,
    data_hora                TIMESTAMP      NOT NULL,
    mes_referencia           CHAR(6)        NOT NULL,
    periodo_comercializacao  INTEGER        NOT NULL,
    pld_rs_mwh               NUMERIC(10,2)  NOT NULL,
    resource_id              VARCHAR(64)    NOT NULL,
    id_raw                   BIGINT         NOT NULL,
    carregado_em             TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (cod_submercado, data_hora)
);
COMMENT ON TABLE tratado.pld_horario IS 'PLD tratado. Grao: 1 submercado x 1 hora (inicio da hora, horario de Brasilia). Valor em R$/MWh.';

CREATE TABLE IF NOT EXISTS tratado.clima_horario (
    cod_usina          VARCHAR(12)   NOT NULL,
    data_hora          TIMESTAMP     NOT NULL,
    temperatura_c      NUMERIC(6,2),
    precipitacao_mm    NUMERIC(7,2),
    nebulosidade_pct   NUMERIC(5,1),
    radiacao_w_m2      NUMERIC(7,1),
    vento_100m_ms      NUMERIC(6,2),
    id_raw             BIGINT        NOT NULL,
    carregado_em       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (cod_usina, data_hora)
);
COMMENT ON TABLE tratado.clima_horario IS 'Clima horario do Open-Meteo nas coordenadas de cada usina. Grao: 1 usina (ponto) x 1 hora.';

CREATE TABLE IF NOT EXISTS qualidade.regra (
    cod_regra      VARCHAR(20)  PRIMARY KEY,
    dimensao       VARCHAR(30)  NOT NULL,
    tabela         VARCHAR(60)  NOT NULL,
    descricao      TEXT         NOT NULL,
    acao           VARCHAR(20)  NOT NULL CHECK (acao IN ('CORRIGIR','DESCARTAR','QUARENTENA','SINALIZAR','COMPLEMENTAR')),
    justificativa  TEXT         NOT NULL
);

CREATE TABLE IF NOT EXISTS qualidade.metrica (
    id_metrica           BIGSERIAL PRIMARY KEY,
    id_execucao          INTEGER      NOT NULL REFERENCES controle.log_execucao(id_execucao),
    cod_regra            VARCHAR(20)  NOT NULL REFERENCES qualidade.regra(cod_regra),
    dimensao             VARCHAR(30)  NOT NULL,
    tabela               VARCHAR(60)  NOT NULL,
    registros_avaliados  INTEGER      NOT NULL,
    registros_falha      INTEGER      NOT NULL,
    percentual_falha     NUMERIC(7,3) NOT NULL,
    executado_em         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE qualidade.metrica IS 'Resultado de cada regra de qualidade em cada execucao. Grao: 1 regra x 1 execucao.';

CREATE TABLE IF NOT EXISTS qualidade.ocorrencia (
    id_ocorrencia  BIGSERIAL PRIMARY KEY,
    id_execucao    INTEGER      NOT NULL REFERENCES controle.log_execucao(id_execucao),
    cod_regra      VARCHAR(20)  NOT NULL REFERENCES qualidade.regra(cod_regra),
    tabela         VARCHAR(60)  NOT NULL,
    chave          JSONB        NOT NULL,
    detalhe        JSONB
);
COMMENT ON TABLE qualidade.ocorrencia IS 'Cada registro que falhou em cada regra (evidencia rastreavel).';

CREATE TABLE IF NOT EXISTS qualidade.quarentena (
    id_quarentena  BIGSERIAL PRIMARY KEY,
    id_execucao    INTEGER      NOT NULL REFERENCES controle.log_execucao(id_execucao),
    tabela_origem  VARCHAR(60)  NOT NULL,
    cod_regra      VARCHAR(20)  NOT NULL REFERENCES qualidade.regra(cod_regra),
    registro       JSONB        NOT NULL,
    motivo         TEXT         NOT NULL,
    quarentenado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE qualidade.quarentena IS 'Registros retirados do caminho ate o DW, guardados integralmente para analise.';

CREATE TABLE IF NOT EXISTS qualidade.profiling (
    id_execucao   INTEGER      NOT NULL REFERENCES controle.log_execucao(id_execucao),
    tabela        VARCHAR(60)  NOT NULL,
    coluna        VARCHAR(60)  NOT NULL,
    tipo          VARCHAR(40),
    total         INTEGER,
    nulos         INTEGER,
    pct_nulos     NUMERIC(7,3),
    distintos     INTEGER,
    minimo        TEXT,
    maximo        TEXT,
    media         NUMERIC(18,4),
    desvio        NUMERIC(18,4),
    p05           NUMERIC(18,4),
    p50           NUMERIC(18,4),
    p95           NUMERIC(18,4),
    mais_frequente TEXT,
    executado_em  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS qualidade.impacto_limpeza (
    id_execucao  INTEGER        NOT NULL REFERENCES controle.log_execucao(id_execucao),
    indicador    VARCHAR(60)    NOT NULL,
    recorte      VARCHAR(60)    NOT NULL,
    antes        NUMERIC(20,4),
    depois       NUMERIC(20,4),
    diferenca    NUMERIC(20,4),
    pct_variacao NUMERIC(10,4),
    executado_em TIMESTAMPTZ    NOT NULL DEFAULT now()
);
COMMENT ON TABLE qualidade.impacto_limpeza IS 'Indicadores de negocio calculados antes (dado bruto) e depois da limpeza.';

CREATE TABLE IF NOT EXISTS tratado.submercado (
    cod_submercado CHAR(2) PRIMARY KEY, nome VARCHAR(40), regioes VARCHAR(80)
);
CREATE TABLE IF NOT EXISTS tratado.fonte_energia (
    id_fonte SMALLINT PRIMARY KEY, cod_fonte VARCHAR(10), descricao VARCHAR(40), renovavel BOOLEAN, intermitente BOOLEAN
);
CREATE TABLE IF NOT EXISTS tratado.usina (
    id_usina INTEGER PRIMARY KEY, cod_usina VARCHAR(12) NOT NULL UNIQUE, nome VARCHAR(80), id_fonte SMALLINT,
    cod_submercado CHAR(2), uf CHAR(2), municipio VARCHAR(60), latitude NUMERIC(9,6), longitude NUMERIC(9,6),
    potencia_mw NUMERIC(8,2), data_inicio_operacao DATE, situacao VARCHAR(20),
    flag_qualidade VARCHAR(200)
);
CREATE TABLE IF NOT EXISTS tratado.mapa_usina (
    id_usina_origem INTEGER PRIMARY KEY, id_usina INTEGER NOT NULL, motivo VARCHAR(120)
);
COMMENT ON TABLE tratado.mapa_usina IS 'De-para de ids de usina da origem para o id canonico (resolve cadastro duplicado).';
CREATE TABLE IF NOT EXISTS tratado.feriado (
    data DATE PRIMARY KEY, descricao VARCHAR(60), tipo VARCHAR(20), origem VARCHAR(20)
);
CREATE TABLE IF NOT EXISTS tratado.parada_usina (
    id_parada INTEGER PRIMARY KEY, id_usina INTEGER NOT NULL, inicio TIMESTAMP NOT NULL, fim TIMESTAMP NOT NULL,
    tipo VARCHAR(20), motivo VARCHAR(120)
);
CREATE TABLE IF NOT EXISTS tratado.medicao_geracao (
    id_medicao BIGINT PRIMARY KEY, id_usina INTEGER, data_hora TIMESTAMP NOT NULL,
    energia_mwh NUMERIC(12,3), energia_original_mwh NUMERIC(14,3), disponibilidade_mw NUMERIC(8,2),
    origem VARCHAR(20), recebido_em TIMESTAMP, status_qualidade VARCHAR(20) NOT NULL,
    regras_aplicadas VARCHAR(200)
);
COMMENT ON TABLE tratado.medicao_geracao IS 'Medicao limpa. Grao: 1 usina x 1 hora. status_qualidade: OK, CORRIGIDO, ESTIMADO, SINALIZADO, DESCONHECIDA.';

CREATE TABLE IF NOT EXISTS controle.limite_pld (
    ano        INTEGER PRIMARY KEY,
    pld_piso   NUMERIC(10,2) NOT NULL,
    pld_teto   NUMERIC(10,2) NOT NULL,
    fonte      VARCHAR(120)
);
COMMENT ON TABLE controle.limite_pld IS 'Limites regulatorios do PLD por ano (ANEEL), carregados do config.ini.';
