import configparser
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
PASTA_SQL = RAIZ / "sql"
PASTA_CONFIG = RAIZ / "config"
PASTA_DOCS = RAIZ / "docs"

load_dotenv(RAIZ / ".env")

_ini = configparser.ConfigParser()
_ini.optionxform = str
_ini.read(PASTA_CONFIG / "config.ini", encoding="utf-8")


def valor(secao, chave, padrao=None):
    variavel = f"{secao}_{chave}".upper()
    if os.getenv(variavel):
        return os.getenv(variavel)
    return _ini.get(secao, chave, fallback=padrao)


def lista(secao, chave):
    texto = valor(secao, chave, "") or ""
    return [item.strip() for item in texto.split(",") if item.strip()]


def url_banco():
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url
    usuario = os.getenv("DB_USER", "postgres")
    senha = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = os.getenv("DB_HOST", "localhost")
    porta = os.getenv("DB_PORT", "5432")
    nome = os.getenv("DB_NAME", "campo_real_energia")
    ssl = os.getenv("DB_SSLMODE", "prefer")
    return f"postgresql+psycopg2://{usuario}:{senha}@{host}:{porta}/{nome}?sslmode={ssl}"


SCHEMA_ORIGEM = valor("banco", "schema_origem", "public")


def http():
    return {
        "timeout": float(valor("http", "timeout_segundos", 60)),
        "tentativas": int(valor("http", "tentativas", 5)),
        "espera_inicial": float(valor("http", "espera_inicial_segundos", 2)),
        "pausa": float(valor("http", "pausa_entre_requisicoes_segundos", 0.5)),
    }


def ccee():
    ids = {}
    for par in lista("ccee", "resource_ids"):
        ano, rid = par.split(":", 1)
        ids[int(ano)] = rid.strip()
    return {
        "url_base": valor("ccee", "url_base").rstrip("/"),
        "dataset": valor("ccee", "dataset"),
        "anos": [int(a) for a in lista("ccee", "anos")],
        "resource_ids": ids,
        "tamanho_pagina": int(valor("ccee", "tamanho_pagina", 5000)),
        "colunas_esperadas": lista("ccee", "colunas_esperadas"),
    }


def openmeteo():
    return {
        "url": valor("openmeteo", "url"),
        "data_inicio": valor("openmeteo", "data_inicio"),
        "data_fim": valor("openmeteo", "data_fim"),
        "variaveis": lista("openmeteo", "variaveis"),
        "fuso": valor("openmeteo", "fuso", "America/Sao_Paulo"),
    }


def limites_pld():
    limites = {}
    if _ini.has_section("limites_pld"):
        for ano, texto in _ini.items("limites_pld"):
            piso, teto = [float(x) for x in texto.split(",")]
            limites[int(ano)] = (piso, teto)
    return limites


def qualidade():
    return {
        "periodo_inicio": valor("qualidade", "periodo_inicio"),
        "periodo_fim": valor("qualidade", "periodo_fim"),
        "atraso_maximo_horas": float(valor("qualidade", "atraso_maximo_horas", 48)),
        "horas_sensor_travado": int(valor("qualidade", "horas_sensor_travado", 12)),
        "lacuna_maxima_interpolacao": int(valor("qualidade", "lacuna_maxima_interpolacao", 6)),
    }
