INSERT INTO dw_campo_real.dim_tempo (sk_tempo, nome_mes, faixa_horaria, estacao_ano, periodo_hidrologico, patamar_carga)
VALUES (-1, 'Desconhecido', 'N/D', 'N/D', 'N/D', 'N/D')
ON CONFLICT (sk_tempo) DO NOTHING;

WITH limites AS (
    SELECT date_trunc('year', LEAST(
               (SELECT min(data_hora) FROM tratado.medicao_geracao),
               (SELECT min(data_hora) FROM tratado.pld_horario))) AS inicio,
           date_trunc('year', GREATEST(
               (SELECT max(data_hora) FROM tratado.medicao_geracao),
               (SELECT max(data_hora) FROM tratado.pld_horario))) + INTERVAL '1 year' - INTERVAL '1 hour' AS fim
), horas AS (
    SELECT generate_series(l.inicio, l.fim, INTERVAL '1 hour') AS dh FROM limites l
), base AS (
    SELECT h.dh,
           h.dh::date AS d,
           EXTRACT(HOUR FROM h.dh)::int AS hr,
           EXTRACT(ISODOW FROM h.dh)::int AS isodow,
           EXTRACT(MONTH FROM h.dh)::int AS mes,
           EXTRACT(MONTH FROM h.dh)::int * 100 + EXTRACT(DAY FROM h.dh)::int AS mmdd,
           f.descricao AS feriado
      FROM horas h
      LEFT JOIN tratado.feriado f ON f.data = h.dh::date
), atributos AS (
    SELECT b.*,
           (b.isodow IN (6, 7)) AS fds,
           (b.feriado IS NOT NULL) AS fer,
           (b.isodow BETWEEN 1 AND 5 AND b.feriado IS NULL) AS util
      FROM base b
)
INSERT INTO dw_campo_real.dim_tempo
SELECT to_char(a.dh, 'YYYYMMDDHH24')::int,
       a.dh,
       a.d,
       EXTRACT(YEAR FROM a.dh)::smallint,
       CASE WHEN a.mes <= 6 THEN 1 ELSE 2 END,
       EXTRACT(QUARTER FROM a.dh)::smallint,
       a.mes,
       (ARRAY['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'])[a.mes],
       (ARRAY['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'])[a.mes],
       to_char(a.dh, 'YYYY-MM'),
       EXTRACT(DAY FROM a.dh)::smallint,
       a.isodow,
       (ARRAY['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'])[a.isodow],
       a.hr,
       CASE WHEN a.hr < 6 THEN 'Madrugada' WHEN a.hr < 12 THEN 'Manhã' WHEN a.hr < 18 THEN 'Tarde' ELSE 'Noite' END,
       a.fds,
       a.fer,
       a.feriado,
       a.util,
       CASE WHEN a.mmdd >= 1221 OR a.mmdd < 321 THEN 'Verão'
            WHEN a.mmdd < 621 THEN 'Outono'
            WHEN a.mmdd < 923 THEN 'Inverno'
            ELSE 'Primavera' END,
       CASE WHEN a.mes IN (12, 1, 2, 3, 4) THEN 'Úmido' ELSE 'Seco' END,
       CASE WHEN a.util AND a.hr BETWEEN 18 AND 20 THEN 'Pesado'
            WHEN a.util AND a.hr BETWEEN 7 AND 23 THEN 'Médio'
            WHEN a.isodow = 6 AND NOT a.fer AND a.hr BETWEEN 7 AND 23 THEN 'Médio'
            WHEN (a.isodow = 7 OR a.fer) AND a.hr BETWEEN 17 AND 21 THEN 'Médio'
            ELSE 'Leve' END,
       (a.util AND a.hr BETWEEN 18 AND 20),
       (a.hr BETWEEN 6 AND 18)
  FROM atributos a
ON CONFLICT (sk_tempo) DO UPDATE SET
       flag_feriado = EXCLUDED.flag_feriado,
       nome_feriado = EXCLUDED.nome_feriado,
       flag_dia_util = EXCLUDED.flag_dia_util,
       patamar_carga = EXCLUDED.patamar_carga,
       flag_horario_ponta = EXCLUDED.flag_horario_ponta;

INSERT INTO dw_campo_real.dim_submercado VALUES (-1, '??', 'Desconhecido', 'Desconhecido')
ON CONFLICT (sk_submercado) DO NOTHING;

INSERT INTO dw_campo_real.dim_submercado (sk_submercado, cod_submercado, nome, regioes)
SELECT CASE s.cod_submercado WHEN 'SE' THEN 1 WHEN 'S' THEN 2 WHEN 'NE' THEN 3 WHEN 'N' THEN 4 END,
       s.cod_submercado, s.nome, s.regioes
  FROM tratado.submercado s
ON CONFLICT (sk_submercado) DO UPDATE SET nome = EXCLUDED.nome, regioes = EXCLUDED.regioes;

INSERT INTO dw_campo_real.dim_usina (sk_usina, cod_usina, nome, valido_de, valido_ate, versao, flag_atual)
VALUES (-1, 'DESCONHECIDA', 'Usina desconhecida', DATE '1900-01-01', DATE '9999-12-31', 1, TRUE)
ON CONFLICT (sk_usina) DO NOTHING;

CALL dw_campo_real.sp_carregar_dim_usina();

INSERT INTO dw_campo_real.dim_regra_qualidade (sk_regra, cod_regra, dimensao, tabela, descricao, acao, justificativa)
SELECT row_number() OVER (ORDER BY cod_regra), cod_regra, dimensao, tabela, descricao, acao, justificativa
  FROM qualidade.regra
ON CONFLICT (cod_regra) DO UPDATE SET dimensao = EXCLUDED.dimensao, tabela = EXCLUDED.tabela,
       descricao = EXCLUDED.descricao, acao = EXCLUDED.acao, justificativa = EXCLUDED.justificativa;

TRUNCATE dw_campo_real.fato_geracao_horaria, dw_campo_real.fato_pld_horario, dw_campo_real.fato_clima_horario,
         dw_campo_real.fato_parada_horaria, dw_campo_real.fato_qualidade_regra, dw_campo_real.agg_impacto_limpeza;

CREATE TEMP TABLE stg_pld_mes ON COMMIT DROP AS
SELECT cod_submercado, date_trunc('month', data_hora) AS mes, avg(pld_rs_mwh) AS pld_medio_mes
  FROM tratado.pld_horario
 GROUP BY 1, 2;

INSERT INTO dw_campo_real.fato_pld_horario (sk_tempo, sk_submercado, pld_rs_mwh, flag_piso, flag_teto, origem_pld)
SELECT t.sk_tempo, s.sk_submercado, p.pld_rs_mwh,
       COALESCE(p.pld_rs_mwh <= l.pld_piso + 0.005, FALSE),
       COALESCE(p.pld_rs_mwh >= l.pld_teto - 0.005, FALSE),
       CASE WHEN p.resource_id = 'SIMULADO' THEN 'SIMULADO' ELSE 'CCEE' END
  FROM tratado.pld_horario p
  JOIN dw_campo_real.dim_tempo t ON t.data_hora = p.data_hora
  JOIN dw_campo_real.dim_submercado s ON s.cod_submercado = p.cod_submercado
  LEFT JOIN controle.limite_pld l ON l.ano = EXTRACT(YEAR FROM p.data_hora)::int;

INSERT INTO dw_campo_real.fato_geracao_horaria (id_medicao, sk_tempo, sk_usina, sk_submercado, energia_mwh, energia_original_mwh,
       disponibilidade_mw, capacidade_mwh, pld_rs_mwh, receita_rs, receita_perfil_plano_rs, flag_em_parada, status_qualidade,
       regras_aplicadas, origem_pld)
SELECT m.id_medicao,
       COALESCE(t.sk_tempo, -1),
       COALESCE(d.sk_usina, -1),
       COALESCE(s.sk_submercado, -1),
       m.energia_mwh,
       m.energia_original_mwh,
       m.disponibilidade_mw,
       CASE WHEN d.sk_usina IS NOT NULL THEN d.potencia_mw END,
       p.pld_rs_mwh,
       ROUND(m.energia_mwh * p.pld_rs_mwh, 2),
       ROUND(m.energia_mwh * pm.pld_medio_mes, 2),
       EXISTS (SELECT 1 FROM tratado.parada_usina pa WHERE pa.id_usina = m.id_usina AND m.data_hora BETWEEN pa.inicio AND pa.fim),
       m.status_qualidade,
       m.regras_aplicadas,
       CASE WHEN p.resource_id = 'SIMULADO' THEN 'SIMULADO' WHEN p.resource_id IS NOT NULL THEN 'CCEE' END
  FROM tratado.medicao_geracao m
  LEFT JOIN tratado.usina u ON u.id_usina = m.id_usina
  LEFT JOIN dw_campo_real.dim_usina d ON d.cod_usina = u.cod_usina AND m.data_hora::date BETWEEN d.valido_de AND d.valido_ate
  LEFT JOIN dw_campo_real.dim_submercado s ON s.cod_submercado = u.cod_submercado
  LEFT JOIN dw_campo_real.dim_tempo t ON t.data_hora = m.data_hora
  LEFT JOIN tratado.pld_horario p ON p.cod_submercado = u.cod_submercado AND p.data_hora = m.data_hora
  LEFT JOIN stg_pld_mes pm ON pm.cod_submercado = u.cod_submercado AND pm.mes = date_trunc('month', m.data_hora);

INSERT INTO dw_campo_real.fato_clima_horario
SELECT t.sk_tempo, d.sk_usina, COALESCE(s.sk_submercado, -1),
       c.temperatura_c, c.precipitacao_mm, c.nebulosidade_pct, c.radiacao_w_m2, c.vento_100m_ms
  FROM tratado.clima_horario c
  JOIN tratado.usina u ON u.cod_usina = c.cod_usina
  JOIN dw_campo_real.dim_usina d ON d.cod_usina = c.cod_usina AND c.data_hora::date BETWEEN d.valido_de AND d.valido_ate
  LEFT JOIN dw_campo_real.dim_submercado s ON s.cod_submercado = u.cod_submercado
  JOIN dw_campo_real.dim_tempo t ON t.data_hora = c.data_hora;

CREATE TEMP TABLE stg_referencia_hora ON COMMIT DROP AS
SELECT m.id_usina, EXTRACT(MONTH FROM m.data_hora)::int AS mes, EXTRACT(HOUR FROM m.data_hora)::int AS hora,
       avg(m.energia_mwh) AS energia_media
  FROM tratado.medicao_geracao m
 WHERE m.status_qualidade <> 'DESCONHECIDA'
   AND m.energia_mwh IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM tratado.parada_usina pa WHERE pa.id_usina = m.id_usina AND m.data_hora BETWEEN pa.inicio AND pa.fim)
 GROUP BY 1, 2, 3;

INSERT INTO dw_campo_real.fato_parada_horaria
SELECT DISTINCT ON (t.sk_tempo, d.sk_usina)
       t.sk_tempo, d.sk_usina, COALESCE(s.sk_submercado, -1),
       pa.id_parada, pa.tipo, pa.motivo, 1,
       COALESCE(r.energia_media, 0)::numeric(12,3),
       p.pld_rs_mwh,
       ROUND(COALESCE(r.energia_media, 0) * p.pld_rs_mwh, 2),
       r.energia_media IS NULL
  FROM tratado.parada_usina pa
  JOIN tratado.usina u ON u.id_usina = pa.id_usina
  CROSS JOIN LATERAL generate_series(pa.inicio, pa.fim, INTERVAL '1 hour') AS h(data_hora)
  JOIN dw_campo_real.dim_tempo t ON t.data_hora = h.data_hora
  JOIN dw_campo_real.dim_usina d ON d.cod_usina = u.cod_usina AND h.data_hora::date BETWEEN d.valido_de AND d.valido_ate
  LEFT JOIN dw_campo_real.dim_submercado s ON s.cod_submercado = u.cod_submercado
  LEFT JOIN tratado.pld_horario p ON p.cod_submercado = u.cod_submercado AND p.data_hora = h.data_hora
  LEFT JOIN stg_referencia_hora r ON r.id_usina = pa.id_usina AND r.mes = EXTRACT(MONTH FROM h.data_hora)::int AND r.hora = EXTRACT(HOUR FROM h.data_hora)::int
 ORDER BY t.sk_tempo, d.sk_usina, pa.id_parada;

INSERT INTO dw_campo_real.fato_qualidade_regra
SELECT m.id_execucao, r.sk_regra,
       to_char(m.executado_em AT TIME ZONE 'America/Sao_Paulo', 'YYYYMMDDHH24')::int,
       m.executado_em, m.registros_avaliados, m.registros_falha, m.percentual_falha,
       m.id_execucao = max(m.id_execucao) OVER (PARTITION BY m.cod_regra)
  FROM qualidade.metrica m
  JOIN dw_campo_real.dim_regra_qualidade r ON r.cod_regra = m.cod_regra;

INSERT INTO dw_campo_real.agg_impacto_limpeza
SELECT i.indicador,
       CASE WHEN i.recorte = 'TOTAL' THEN 'TOTAL' ELSE split_part(i.recorte, ':', 1) END,
       CASE WHEN i.recorte = 'TOTAL' THEN 'TOTAL' ELSE split_part(i.recorte, ':', 2) END,
       i.antes, i.depois, i.diferenca, i.pct_variacao
  FROM qualidade.impacto_limpeza i
 WHERE i.id_execucao = (SELECT max(id_execucao) FROM qualidade.impacto_limpeza);
