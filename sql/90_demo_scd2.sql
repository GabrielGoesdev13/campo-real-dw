BEGIN;

SELECT sk_usina, cod_usina, nome, potencia_mw, valido_de, valido_ate, versao, flag_atual
  FROM dw_campo_real.dim_usina
 WHERE cod_usina = 'CRE-UHE-001';

UPDATE tratado.usina SET potencia_mw = 200.00 WHERE cod_usina = 'CRE-UHE-001';
UPDATE tratado.usina SET municipio = 'Cap. Leônidas Marques' WHERE cod_usina = 'CRE-UHE-001';

CALL dw_campo_real.sp_carregar_dim_usina();

SELECT sk_usina, cod_usina, nome, municipio, potencia_mw, valido_de, valido_ate, versao, flag_atual
  FROM dw_campo_real.dim_usina
 WHERE cod_usina = 'CRE-UHE-001'
 ORDER BY versao;

ROLLBACK;
