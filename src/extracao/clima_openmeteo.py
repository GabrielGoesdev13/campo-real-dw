import logging

import pandas as pd

from src import config, db
from src.http_client import ClienteHttp, ErroEsquema
from src.log_execucao import registrar

log = logging.getLogger(__name__)

RENOMEAR = {
    "temperature_2m": "temperatura_c",
    "precipitation": "precipitacao_mm",
    "cloud_cover": "nebulosidade_pct",
    "shortwave_radiation": "radiacao_w_m2",
    "wind_speed_100m": "vento_100m_ms",
}


def _usinas():
    return db.consultar(
        "SELECT cod_usina, latitude, longitude FROM tratado.usina WHERE latitude IS NOT NULL ORDER BY cod_usina"
    )


def extrair(forcar=False):
    cfg = config.openmeteo()
    cliente = ClienteHttp(**config.http())
    usinas = _usinas()
    if usinas.empty:
        raise RuntimeError("tratado.usina esta vazia. Rode a etapa de qualidade antes da extracao de clima.")

    for usina in usinas.itertuples():
        parametros = {
            "latitude": float(usina.latitude),
            "longitude": float(usina.longitude),
            "start_date": cfg["data_inicio"],
            "end_date": cfg["data_fim"],
            "hourly": ",".join(cfg["variaveis"]),
            "timezone": cfg["fuso"],
            "wind_speed_unit": "ms",
        }
        cliente.total_tentativas_extras = 0
        with registrar("extracao_clima", "Open-Meteo", {"cod_usina": usina.cod_usina, **parametros}) as execucao:
            existe = db.escalar(
                """SELECT count(*) FROM raw.openmeteo_clima
                    WHERE cod_usina = :c AND latitude = :lat AND longitude = :lon
                      AND data_inicio = :i AND data_fim = :f""",
                {"c": usina.cod_usina, "lat": usina.latitude, "lon": usina.longitude, "i": cfg["data_inicio"], "f": cfg["data_fim"]},
            )
            if existe and not forcar:
                execucao.status = "CACHE"
                execucao.aviso(f"{usina.cod_usina}: periodo ja baixado anteriormente")
                continue

            resposta = cliente.get_json(cfg["url"], parametros)
            if resposta.get("error"):
                raise RuntimeError(f"Open-Meteo retornou erro: {resposta.get('reason')}")
            horario = resposta.get("hourly") or {}
            tempos = horario.get("time") or []
            if not tempos:
                execucao.status = "SEM_DADOS"
                execucao.aviso(f"{usina.cod_usina}: resposta sem dados horarios")
                continue
            faltando = [v for v in cfg["variaveis"] if v not in horario]
            if faltando:
                raise ErroEsquema(f"Variaveis ausentes na resposta: {faltando}")

            execucao.linhas_lidas = len(tempos)
            db.inserir_lote(
                "raw.openmeteo_clima",
                ["cod_usina", "latitude", "longitude", "data_inicio", "data_fim", "parametros", "resposta", "url_origem", "id_execucao"],
                [(usina.cod_usina, usina.latitude, usina.longitude, cfg["data_inicio"], cfg["data_fim"], parametros, resposta, cfg["url"], execucao.id)],
                """ON CONFLICT (cod_usina, latitude, longitude, data_inicio, data_fim)
                   DO UPDATE SET resposta = EXCLUDED.resposta, extraido_em = now(), id_execucao = EXCLUDED.id_execucao""",
            )
            execucao.linhas_gravadas = len(tempos)
            if cliente.total_tentativas_extras:
                execucao.aviso(f"{cliente.total_tentativas_extras} novas tentativas HTTP foram necessarias")
    transformar()


def transformar():
    with registrar("transformacao_clima", "raw.openmeteo_clima") as execucao:
        raw = db.consultar(
            """SELECT DISTINCT ON (r.cod_usina) r.id_raw, r.cod_usina, r.resposta
                 FROM raw.openmeteo_clima r
                 JOIN tratado.usina u ON u.cod_usina = r.cod_usina
                                      AND u.latitude = r.latitude AND u.longitude = r.longitude
                ORDER BY r.cod_usina, r.extraido_em DESC"""
        )
        partes = []
        for linha in raw.itertuples():
            horario = linha.resposta["hourly"]
            df = pd.DataFrame(horario).rename(columns={"time": "data_hora", **RENOMEAR})
            df["data_hora"] = pd.to_datetime(df["data_hora"])
            df["cod_usina"] = linha.cod_usina
            df["id_raw"] = linha.id_raw
            partes.append(df)
        if not partes:
            execucao.status = "SEM_DADOS"
            return
        clima = pd.concat(partes, ignore_index=True)
        colunas = ["cod_usina", "data_hora", *[c for c in RENOMEAR.values() if c in clima.columns], "id_raw"]
        clima = clima[colunas].drop_duplicates(["cod_usina", "data_hora"])
        execucao.linhas_lidas = len(clima)
        db.executar("TRUNCATE tratado.clima_horario")
        execucao.linhas_gravadas = db.inserir_dataframe("tratado.clima_horario", clima)
