CREATE SCHEMA IF NOT EXISTS dw_campo_real;

CREATE TABLE IF NOT EXISTS dw_campo_real.dim_tempo (
    sk_tempo             INTEGER      PRIMARY KEY,
    data_hora            TIMESTAMP    UNIQUE,
    data                 DATE,
    ano                  SMALLINT,
    semestre             SMALLINT,
    trimestre            SMALLINT,
    mes                  SMALLINT,
    nome_mes             VARCHAR(12),
    mes_abrev            CHAR(3),
    ano_mes              CHAR(7),
    dia                  SMALLINT,
    dia_semana           SMALLINT,
    nome_dia_semana      VARCHAR(15),
    hora                 SMALLINT,
    faixa_horaria        VARCHAR(10),
    flag_fim_de_semana   BOOLEAN,
    flag_feriado         BOOLEAN,
    nome_feriado         VARCHAR(60),
    flag_dia_util        BOOLEAN,
    estacao_ano          VARCHAR(10),
    periodo_hidrologico  VARCHAR(10),
    patamar_carga        VARCHAR(10),
    flag_horario_ponta   BOOLEAN,
    flag_horario_solar   BOOLEAN
);
COMMENT ON TABLE dw_campo_real.dim_tempo IS 'Dimensao de tempo. Grao: 1 hora (horario de Brasilia). sk_tempo = AAAAMMDDHH; -1 = desconhecido.';

CREATE TABLE IF NOT EXISTS dw_campo_real.dim_submercado (
    sk_submercado   SMALLINT     PRIMARY KEY,
    cod_submercado  CHAR(2)      NOT NULL UNIQUE,
    nome            VARCHAR(40)  NOT NULL,
    regioes         VARCHAR(80)
);
COMMENT ON TABLE dw_campo_real.dim_submercado IS 'Submercados do SIN. Dimensao conformada entre geracao, preco, clima e paradas. -1 = desconhecido.';

CREATE TABLE IF NOT EXISTS dw_campo_real.dim_usina (
    sk_usina              INTEGER       PRIMARY KEY,
    cod_usina             VARCHAR(12)   NOT NULL,
    nome                  VARCHAR(80)   NOT NULL,
    cod_fonte             VARCHAR(10),
    fonte                 VARCHAR(40),
    renovavel             BOOLEAN,
    intermitente          BOOLEAN,
    cod_submercado        CHAR(2),
    uf                    CHAR(2),
    municipio             VARCHAR(60),
    latitude              NUMERIC(9,6),
    longitude             NUMERIC(9,6),
    potencia_mw           NUMERIC(8,2),
    data_inicio_operacao  DATE,
    situacao              VARCHAR(20),
    flag_qualidade        VARCHAR(200),
    valido_de             DATE          NOT NULL,
    valido_ate            DATE          NOT NULL,
    versao                SMALLINT      NOT NULL,
    flag_atual            BOOLEAN       NOT NULL,
    hash_scd2             CHAR(32)
);
CREATE SEQUENCE IF NOT EXISTS dw_campo_real.seq_dim_usina START 1;
CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_usina_versao ON dw_campo_real.dim_usina (cod_usina, versao);
COMMENT ON TABLE dw_campo_real.dim_usina IS 'Usinas com fonte desnormalizada. SCD tipo 2 para nome, potencia, situacao, fonte e submercado; tipo 1 para correcoes de cadastro (UF, municipio, coordenadas, data de inicio). -1 = desconhecida.';

CREATE TABLE IF NOT EXISTS dw_campo_real.dim_regra_qualidade (
    sk_regra       SMALLINT     PRIMARY KEY,
    cod_regra      VARCHAR(20)  NOT NULL UNIQUE,
    dimensao       VARCHAR(30)  NOT NULL,
    tabela         VARCHAR(60)  NOT NULL,
    descricao      TEXT         NOT NULL,
    acao           VARCHAR(20)  NOT NULL,
    justificativa  TEXT         NOT NULL
);
COMMENT ON TABLE dw_campo_real.dim_regra_qualidade IS 'Catalogo das regras de qualidade (dimensao de qualidade, tabela, decisao e justificativa).';

CREATE TABLE IF NOT EXISTS dw_campo_real.fato_geracao_horaria (
    id_medicao               BIGINT         PRIMARY KEY,
    sk_tempo                 INTEGER        NOT NULL REFERENCES dw_campo_real.dim_tempo,
    sk_usina                 INTEGER        NOT NULL REFERENCES dw_campo_real.dim_usina,
    sk_submercado            SMALLINT       NOT NULL REFERENCES dw_campo_real.dim_submercado,
    energia_mwh              NUMERIC(12,3),
    energia_original_mwh     NUMERIC(14,3),
    disponibilidade_mw       NUMERIC(8,2),
    capacidade_mwh           NUMERIC(8,2),
    pld_rs_mwh               NUMERIC(10,2),
    receita_rs               NUMERIC(16,2),
    receita_perfil_plano_rs  NUMERIC(16,2),
    flag_em_parada           BOOLEAN        NOT NULL,
    status_qualidade         VARCHAR(20)    NOT NULL,
    regras_aplicadas         VARCHAR(200)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_fato_geracao_grao ON dw_campo_real.fato_geracao_horaria (sk_tempo, sk_usina) WHERE sk_usina <> -1;
CREATE INDEX IF NOT EXISTS ix_fato_geracao_usina ON dw_campo_real.fato_geracao_horaria (sk_usina);
COMMENT ON TABLE dw_campo_real.fato_geracao_horaria IS 'GRAO: 1 usina x 1 hora. Energia medida (MWh) apos limpeza, valorada ao PLD do submercado da usina na mesma hora. Medidas aditivas: energia, capacidade, receita, receita_perfil_plano.';

CREATE TABLE IF NOT EXISTS dw_campo_real.fato_pld_horario (
    sk_tempo        INTEGER        NOT NULL REFERENCES dw_campo_real.dim_tempo,
    sk_submercado   SMALLINT       NOT NULL REFERENCES dw_campo_real.dim_submercado,
    pld_rs_mwh      NUMERIC(10,2)  NOT NULL,
    flag_piso       BOOLEAN        NOT NULL,
    flag_teto       BOOLEAN        NOT NULL,
    PRIMARY KEY (sk_tempo, sk_submercado)
);
ALTER TABLE dw_campo_real.fato_pld_horario ADD COLUMN IF NOT EXISTS origem_pld VARCHAR(10) NOT NULL DEFAULT 'CCEE';
ALTER TABLE dw_campo_real.fato_geracao_horaria ADD COLUMN IF NOT EXISTS origem_pld VARCHAR(10);
COMMENT ON TABLE dw_campo_real.fato_pld_horario IS 'GRAO: 1 submercado x 1 hora. PLD horario da CCEE em R$/MWh (2025 e 2026). Medida nao aditiva: usar media.';

CREATE TABLE IF NOT EXISTS dw_campo_real.fato_clima_horario (
    sk_tempo          INTEGER       NOT NULL REFERENCES dw_campo_real.dim_tempo,
    sk_usina          INTEGER       NOT NULL REFERENCES dw_campo_real.dim_usina,
    sk_submercado     SMALLINT      NOT NULL REFERENCES dw_campo_real.dim_submercado,
    temperatura_c     NUMERIC(6,2),
    precipitacao_mm   NUMERIC(7,2),
    nebulosidade_pct  NUMERIC(5,1),
    radiacao_w_m2     NUMERIC(7,1),
    vento_100m_ms     NUMERIC(6,2),
    PRIMARY KEY (sk_tempo, sk_usina)
);
COMMENT ON TABLE dw_campo_real.fato_clima_horario IS 'GRAO: 1 ponto de clima x 1 hora, onde o ponto sao as coordenadas exatas de cada usina (Open-Meteo). Por isso o ponto herda a usina e o submercado. Medidas nao aditivas: usar media (precipitacao pode ser somada).';

CREATE TABLE IF NOT EXISTS dw_campo_real.fato_parada_horaria (
    sk_tempo              INTEGER        NOT NULL REFERENCES dw_campo_real.dim_tempo,
    sk_usina              INTEGER        NOT NULL REFERENCES dw_campo_real.dim_usina,
    sk_submercado         SMALLINT       NOT NULL REFERENCES dw_campo_real.dim_submercado,
    id_parada             INTEGER        NOT NULL,
    tipo_parada           VARCHAR(20)    NOT NULL,
    motivo                VARCHAR(120),
    horas_indisponiveis   SMALLINT       NOT NULL,
    energia_esperada_mwh  NUMERIC(12,3),
    pld_rs_mwh            NUMERIC(10,2),
    receita_perdida_rs    NUMERIC(16,2),
    flag_sem_referencia   BOOLEAN        NOT NULL,
    PRIMARY KEY (sk_tempo, sk_usina)
);
COMMENT ON TABLE dw_campo_real.fato_parada_horaria IS 'GRAO: 1 usina x 1 hora em parada. O evento de parada (inicio-fim) e explodido em horas. Energia esperada = media da mesma usina, mesmo mes e mesma hora do dia fora de parada.';

CREATE TABLE IF NOT EXISTS dw_campo_real.fato_qualidade_regra (
    id_execucao           INTEGER       NOT NULL,
    sk_regra              SMALLINT      NOT NULL REFERENCES dw_campo_real.dim_regra_qualidade,
    sk_tempo_execucao     INTEGER       NOT NULL,
    executado_em          TIMESTAMPTZ   NOT NULL,
    registros_avaliados   INTEGER       NOT NULL,
    registros_falha       INTEGER       NOT NULL,
    percentual_falha      NUMERIC(7,3)  NOT NULL,
    flag_ultima_execucao  BOOLEAN       NOT NULL,
    PRIMARY KEY (id_execucao, sk_regra)
);
COMMENT ON TABLE dw_campo_real.fato_qualidade_regra IS 'GRAO: 1 regra de qualidade x 1 execucao do pipeline.';

CREATE TABLE IF NOT EXISTS dw_campo_real.agg_impacto_limpeza (
    indicador     VARCHAR(60)    NOT NULL,
    recorte_tipo  VARCHAR(10)    NOT NULL,
    recorte       VARCHAR(60)    NOT NULL,
    antes         NUMERIC(20,4),
    depois        NUMERIC(20,4),
    diferenca     NUMERIC(20,4),
    pct_variacao  NUMERIC(10,4),
    PRIMARY KEY (indicador, recorte_tipo, recorte)
);
COMMENT ON TABLE dw_campo_real.agg_impacto_limpeza IS 'Tabela agregada. GRAO: 1 indicador de negocio x 1 recorte (total, fonte ou usina), na ultima execucao da qualidade.';

CREATE OR REPLACE PROCEDURE dw_campo_real.sp_carregar_dim_usina()
LANGUAGE plpgsql
AS $$
BEGIN
    DROP TABLE IF EXISTS stg_usina;
    CREATE TEMP TABLE stg_usina AS
    SELECT u.cod_usina, u.nome, f.cod_fonte, f.descricao AS fonte, f.renovavel, f.intermitente,
           u.cod_submercado, u.uf, u.municipio, u.latitude, u.longitude, u.potencia_mw,
           u.data_inicio_operacao, u.situacao, u.flag_qualidade,
           md5(concat_ws('|', u.nome, f.cod_fonte, u.cod_submercado, u.potencia_mw::text, u.situacao)) AS hash_scd2
      FROM tratado.usina u
      JOIN tratado.fonte_energia f ON f.id_fonte = u.id_fonte;

    UPDATE dw_campo_real.dim_usina d
       SET uf = s.uf, municipio = s.municipio, latitude = s.latitude, longitude = s.longitude,
           data_inicio_operacao = s.data_inicio_operacao, flag_qualidade = s.flag_qualidade,
           fonte = s.fonte, renovavel = s.renovavel, intermitente = s.intermitente
      FROM stg_usina s
     WHERE d.cod_usina = s.cod_usina;

    DROP TABLE IF EXISTS stg_usina_mudou;
    CREATE TEMP TABLE stg_usina_mudou AS
    SELECT s.*, d.sk_usina AS sk_anterior, d.versao AS versao_anterior
      FROM stg_usina s
      LEFT JOIN dw_campo_real.dim_usina d ON d.cod_usina = s.cod_usina AND d.flag_atual
     WHERE d.sk_usina IS NULL OR d.hash_scd2 IS DISTINCT FROM s.hash_scd2;

    UPDATE dw_campo_real.dim_usina d
       SET valido_ate = CURRENT_DATE - 1, flag_atual = FALSE
      FROM stg_usina_mudou m
     WHERE d.sk_usina = m.sk_anterior;

    INSERT INTO dw_campo_real.dim_usina
    SELECT nextval('dw_campo_real.seq_dim_usina'), m.cod_usina, m.nome, m.cod_fonte, m.fonte, m.renovavel, m.intermitente,
           m.cod_submercado, m.uf, m.municipio, m.latitude, m.longitude, m.potencia_mw, m.data_inicio_operacao,
           m.situacao, m.flag_qualidade,
           CASE WHEN m.sk_anterior IS NULL THEN DATE '1900-01-01' ELSE CURRENT_DATE END,
           DATE '9999-12-31',
           COALESCE(m.versao_anterior, 0) + 1,
           TRUE,
           m.hash_scd2
      FROM stg_usina_mudou m
     ORDER BY m.cod_usina;

    DROP TABLE IF EXISTS stg_usina;
    DROP TABLE IF EXISTS stg_usina_mudou;
END;
$$;
COMMENT ON PROCEDURE dw_campo_real.sp_carregar_dim_usina() IS 'Carga SCD da dim_usina: tipo 1 (sobrescreve) para correcoes de cadastro e tipo 2 (nova versao) para nome, fonte, submercado, potencia e situacao.';

CREATE OR REPLACE VIEW dw_campo_real.vw_geracao_clima AS
SELECT g.sk_tempo, g.sk_usina, g.sk_submercado, g.energia_mwh, g.capacidade_mwh,
       c.radiacao_w_m2, c.vento_100m_ms, c.temperatura_c, c.precipitacao_mm, c.nebulosidade_pct
  FROM dw_campo_real.fato_geracao_horaria g
  JOIN dw_campo_real.fato_clima_horario c ON c.sk_tempo = g.sk_tempo AND c.sk_usina = g.sk_usina
 WHERE g.sk_usina <> -1 AND NOT g.flag_em_parada;
COMMENT ON VIEW dw_campo_real.vw_geracao_clima IS 'Geracao e clima no mesmo grao (usina x hora), fora de paradas, para correlacoes no painel.';
