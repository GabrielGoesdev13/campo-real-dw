import logging
import math
import zlib

import pandas as pd

from src import db
from src.log_execucao import registrar

log = logging.getLogger(__name__)

SUBMERCADOS = ["SE", "S", "NE", "N"]


def _ruido(cod_submercado, data_hora):
    texto = f"{cod_submercado}{data_hora:%Y-%m-%d %H:%M:%S}"
    return (zlib.crc32(texto.encode("utf-8")) % 1000) / 1000


def _pld(cod_submercado, data_hora):
    doy = data_hora.dayofyear
    hora = data_hora.hour
    valor = (
        120
        + 150 * (1 - math.cos(2 * math.pi * (doy - 60) / 365)) / 2
        - 60 * (10 <= hora <= 15)
        + 90 * (18 <= hora <= 21)
        + 80 * (_ruido(cod_submercado, data_hora) - 0.5)
    )
    return round(min(1500, max(58.60, valor)), 2)


def executar(inicio="2025-01-01 00:00", fim="2025-12-31 23:00"):
    with registrar("pld_simulado", "Plano B do script da professora (passo 4.9)", {"inicio": inicio, "fim": fim}) as execucao:
        horas = pd.date_range(inicio, fim, freq="h")
        linhas = []
        for sub in SUBMERCADOS:
            for dh in horas:
                linhas.append((sub, dh.to_pydatetime(), dh.strftime("%Y%m"), (dh.day - 1) * 24 + dh.hour + 1, _pld(sub, dh), "SIMULADO", 0))
        execucao.linhas_lidas = len(linhas)
        execucao.linhas_gravadas = db.inserir_lote(
            "tratado.pld_horario",
            ["cod_submercado", "data_hora", "mes_referencia", "periodo_comercializacao", "pld_rs_mwh", "resource_id", "id_raw"],
            linhas,
            "ON CONFLICT (cod_submercado, data_hora) DO NOTHING",
        )
        reais = execucao.linhas_lidas - execucao.linhas_gravadas
        execucao.aviso(
            f"PLD SIMULADO gravado em {execucao.linhas_gravadas} horas; {reais} horas ja tinham PLD real da CCEE e foram mantidas. "
            "Ao rodar a etapa 'pld' com a API disponivel, o dado real substitui o simulado."
        )
