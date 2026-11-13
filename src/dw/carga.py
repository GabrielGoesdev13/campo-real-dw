import logging

from src import config, db
from src.log_execucao import registrar

log = logging.getLogger(__name__)

TABELAS = [
    "dim_tempo", "dim_submercado", "dim_usina", "dim_regra_qualidade",
    "fato_geracao_horaria", "fato_pld_horario", "fato_clima_horario", "fato_parada_horaria",
    "fato_qualidade_regra", "agg_impacto_limpeza",
]


def _limites():
    linhas = [(ano, piso, teto, "ANEEL (config.ini)") for ano, (piso, teto) in config.limites_pld().items()]
    db.inserir_lote(
        "controle.limite_pld", ["ano", "pld_piso", "pld_teto", "fonte"], linhas,
        "ON CONFLICT (ano) DO UPDATE SET pld_piso = EXCLUDED.pld_piso, pld_teto = EXCLUDED.pld_teto",
    )


def executar():
    with registrar("carga_dw", "tratado -> dw_campo_real", propagar_erro=True) as execucao:
        db.executar_arquivo("10_dw_ddl.sql")
        _limites()
        db.executar_arquivo("11_dw_carga.sql")
        total = 0
        for tabela in TABELAS:
            linhas = db.escalar(f"SELECT count(*) FROM dw_campo_real.{tabela}")
            log.info("dw_campo_real.%-22s %8s linhas", tabela, linhas)
            total += linhas
        execucao.linhas_gravadas = total
        execucao.linhas_lidas = db.escalar("SELECT count(*) FROM tratado.medicao_geracao") + db.escalar("SELECT count(*) FROM tratado.pld_horario")
        sem_preco = db.escalar("SELECT count(*) FROM dw_campo_real.fato_geracao_horaria WHERE sk_usina <> -1 AND receita_rs IS NULL")
        if sem_preco:
            execucao.aviso(f"{sem_preco} horas de geracao sem PLD (receita nula)")
