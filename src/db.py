import json
from contextlib import contextmanager

import numpy as np
import pandas as pd
from psycopg2.extras import Json, execute_values
from sqlalchemy import create_engine, text

from src import config

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(config.url_banco(), pool_pre_ping=True)
    return _engine


@contextmanager
def conexao_crua():
    con = engine().raw_connection()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def executar(sql, parametros=None):
    with engine().begin() as con:
        return con.execute(text(sql), parametros or {})


def executar_arquivo(nome_arquivo):
    caminho = config.PASTA_SQL / nome_arquivo
    conteudo = caminho.read_text(encoding="utf-8")
    conteudo = conteudo.replace("{{schema_origem}}", config.SCHEMA_ORIGEM)
    with conexao_crua() as con:
        with con.cursor() as cur:
            cur.execute(conteudo)


def consultar(sql, parametros=None):
    with engine().connect() as con:
        return pd.read_sql(text(sql), con, params=parametros or {})


def escalar(sql, parametros=None):
    with engine().begin() as con:
        return con.execute(text(sql), parametros or {}).scalar()


def _converter(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and np.isnan(valor):
        return None
    if valor is pd.NaT:
        return None
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (np.floating,)):
        return None if np.isnan(valor) else float(valor)
    if isinstance(valor, (np.bool_,)):
        return bool(valor)
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    if isinstance(valor, (dict, list)):
        return Json(valor)
    return valor


def inserir_lote(tabela, colunas, linhas, sufixo="", tamanho=5000):
    if not linhas:
        return 0
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES %s {sufixo}"
    total = 0
    with conexao_crua() as con:
        with con.cursor() as cur:
            for i in range(0, len(linhas), tamanho):
                bloco = [tuple(_converter(v) for v in linha) for linha in linhas[i:i + tamanho]]
                execute_values(cur, sql, bloco, page_size=tamanho)
                total += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return total


def inserir_dataframe(tabela, df, sufixo=""):
    if df.empty:
        return 0
    colunas = list(df.columns)
    linhas = df.astype(object).where(pd.notna(df), None).values.tolist()
    return inserir_lote(tabela, colunas, linhas, sufixo)


def substituir_tabela(tabela, df):
    executar(f"TRUNCATE {tabela}")
    return inserir_dataframe(tabela, df)


def para_json(valor):
    return json.dumps(valor, ensure_ascii=False, default=str)
