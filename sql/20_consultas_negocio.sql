SELECT u.fonte, u.cod_usina, s.cod_submercado,
       ROUND(SUM(f.energia_mwh) / 1000, 1)                        AS geracao_gwh,
       ROUND(100 * SUM(f.energia_mwh) / (MAX(u.potencia_mw) * 8760), 1) AS fator_capacidade_pct
  FROM dw_campo_real.fato_geracao_horaria f
  JOIN dw_campo_real.dim_usina u ON u.sk_usina = f.sk_usina
  JOIN dw_campo_real.dim_submercado s ON s.sk_submercado = f.sk_submercado
  JOIN dw_campo_real.dim_tempo t ON t.sk_tempo = f.sk_tempo
 WHERE f.sk_usina <> -1 AND t.ano = 2025
 GROUP BY 1, 2, 3
 ORDER BY 1, 2;

SELECT t.ano_mes, u.fonte, ROUND(SUM(f.energia_mwh)) AS geracao_mwh
  FROM dw_campo_real.fato_geracao_horaria f
  JOIN dw_campo_real.dim_usina u ON u.sk_usina = f.sk_usina
  JOIN dw_campo_real.dim_tempo t ON t.sk_tempo = f.sk_tempo
 WHERE f.sk_usina <> -1
 GROUP BY 1, 2
 ORDER BY 1, 2;

SELECT ROUND(SUM(f.receita_rs) / 1e6, 2) AS receita_valorada_milhoes_rs,
       ROUND(SUM(f.energia_mwh) / 1000, 1) AS geracao_gwh,
       ROUND(SUM(f.receita_rs) / SUM(f.energia_mwh), 2) AS preco_capturado_rs_mwh
  FROM dw_campo_real.fato_geracao_horaria f
 WHERE f.receita_rs IS NOT NULL;

SELECT u.fonte,
       ROUND(SUM(f.receita_rs) / 1e6, 2) AS receita_milhoes_rs,
       ROUND(SUM(f.receita_rs) / SUM(f.energia_mwh), 2) AS preco_capturado_rs_mwh,
       ROUND(SUM(f.receita_perfil_plano_rs) / SUM(f.energia_mwh), 2) AS pld_medio_referencia_rs_mwh,
       ROUND(SUM(f.receita_rs) / SUM(f.receita_perfil_plano_rs), 3) AS razao_de_captura
  FROM dw_campo_real.fato_geracao_horaria f
  JOIN dw_campo_real.dim_usina u ON u.sk_usina = f.sk_usina
 WHERE f.receita_rs IS NOT NULL
 GROUP BY 1
 ORDER BY razao_de_captura DESC;

SELECT t.mes, t.hora, ROUND(AVG(p.pld_rs_mwh), 2) AS pld_medio
  FROM dw_campo_real.fato_pld_horario p
  JOIN dw_campo_real.dim_tempo t ON t.sk_tempo = p.sk_tempo
 WHERE t.ano = 2025
 GROUP BY 1, 2
 ORDER BY 1, 2;

SELECT t.hora, u.fonte, ROUND(AVG(f.energia_mwh / NULLIF(f.capacidade_mwh, 0)) * 100, 1) AS fator_capacidade_medio_pct
  FROM dw_campo_real.fato_geracao_horaria f
  JOIN dw_campo_real.dim_usina u ON u.sk_usina = f.sk_usina
  JOIN dw_campo_real.dim_tempo t ON t.sk_tempo = f.sk_tempo
 WHERE f.sk_usina <> -1
 GROUP BY 1, 2
 ORDER BY 2, 1;

SELECT p.tipo_parada, u.cod_usina, MIN(p.motivo) AS motivo,
       SUM(p.horas_indisponiveis) AS horas_indisponiveis,
       ROUND(SUM(p.energia_esperada_mwh)) AS energia_nao_gerada_mwh,
       ROUND(SUM(p.receita_perdida_rs) / 1e3, 1) AS receita_perdida_mil_rs,
       BOOL_OR(p.flag_sem_referencia) AS sem_referencia
  FROM dw_campo_real.fato_parada_horaria p
  JOIN dw_campo_real.dim_usina u ON u.sk_usina = p.sk_usina
 GROUP BY 1, 2
 ORDER BY 1, receita_perdida_mil_rs DESC;

SELECT u.fonte,
       ROUND(CORR(c.radiacao_w_m2, f.energia_mwh)::numeric, 3) AS corr_radiacao_geracao,
       ROUND(CORR(c.vento_100m_ms, f.energia_mwh)::numeric, 3) AS corr_vento_geracao
  FROM dw_campo_real.fato_geracao_horaria f
  JOIN dw_campo_real.fato_clima_horario c ON c.sk_tempo = f.sk_tempo AND c.sk_usina = f.sk_usina
  JOIN dw_campo_real.dim_usina u ON u.sk_usina = f.sk_usina
 WHERE NOT f.flag_em_parada
 GROUP BY 1
 ORDER BY 1;

SELECT r.dimensao,
       SUM(q.registros_avaliados) AS avaliados,
       SUM(q.registros_falha) AS falhas,
       ROUND(100 - 100.0 * SUM(q.registros_falha) / NULLIF(SUM(q.registros_avaliados), 0), 3) AS indice_qualidade_pct
  FROM dw_campo_real.fato_qualidade_regra q
  JOIN dw_campo_real.dim_regra_qualidade r ON r.sk_regra = q.sk_regra
 WHERE q.flag_ultima_execucao
 GROUP BY 1
 ORDER BY 4;

SELECT indicador, recorte_tipo, recorte, ROUND(antes, 2) AS antes, ROUND(depois, 2) AS depois, ROUND(pct_variacao, 2) AS pct
  FROM dw_campo_real.agg_impacto_limpeza
 WHERE recorte_tipo IN ('TOTAL', 'FONTE')
 ORDER BY indicador, recorte_tipo, recorte;
