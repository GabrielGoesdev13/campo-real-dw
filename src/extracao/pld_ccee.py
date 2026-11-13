import logging
import re
from datetime import datetime

import pandas as pd

from src import config, db
from src.http_client import ClienteHttp, ErroEsquema, ErroExtracao
from src.log_execucao import registrar

log = logging.getLogger(__name__)

MAPA_SUBMERCADO = {
    "SE": "SE", "SUDESTE": "SE", "SUDESTE/CENTRO-OESTE": "SE", "SE/CO": "SE", "SUDESTE/CENTRO OESTE": "SE",
    "S": "S", "SUL": "S",
    "NE": "NE", "NORDESTE": "NE",
    "N": "N", "NORTE": "N",
}


def _cliente():
    return ClienteHttp(**config.http())


def descobrir_recursos(cliente, cfg):
    recursos = dict(cfg["resource_ids"])
    url = f"{cfg['url_base']}/package_show"
    try:
        dados = cliente.get_json(url, {"id": cfg["dataset"]})
        for recurso in dados.get("result", {}).get("resources", []):
            texto = f"{recurso.get('name', '')} {recurso.get('description', '')}"
            ano = re.search(r"(20\d{2})", texto)
            if ano and recurso.get("datastore_active", True):
                recursos[int(ano.group(1))] = recurso["id"]
        log.info("Recursos encontrados no dataset %s: %s", cfg["dataset"], recursos)
    except ErroExtracao as erro:
        log.warning("Nao foi possivel listar o dataset (%s). Usando resource_ids do config.ini", erro)
    return recursos


def _validar_colunas(campos, esperadas):
    recebidas = {c.upper() for c in campos if c != "_id"}
    faltando = {c.upper() for c in esperadas} - recebidas
    extras = recebidas - {c.upper() for c in esperadas}
    if faltando:
        raise ErroEsquema(f"Colunas esperadas ausentes na API: {sorted(faltando)}. Recebidas: {sorted(recebidas)}")
    return extras


def extrair_ano(cliente, cfg, ano, resource_id, forcar=False):
    url = f"{cfg['url_base']}/datastore_search"
    parametros = {"ano": ano, "resource_id": resource_id, "dataset": cfg["dataset"]}
    cliente.total_tentativas_extras = 0
    with registrar("extracao_pld", "CCEE", parametros) as execucao:
        cabecalho = cliente.get_json(url, {"resource_id": resource_id, "limit": 0})
        if not cabecalho.get("success", False):
            raise ErroExtracao(f"API respondeu success=false: {cabecalho.get('error')}")
        resultado = cabecalho["result"]
        total = int(resultado.get("total") or 0)
        campos = [f["id"] for f in resultado.get("fields", [])]
        extras = _validar_colunas(campos, cfg["colunas_esperadas"])
        if extras:
            execucao.aviso(f"Colunas novas na API (ignoradas): {sorted(extras)}")
        if total == 0:
            execucao.status = "SEM_DADOS"
            execucao.aviso(f"Recurso {resource_id} ({ano}) sem registros na API")
            return

        ja_baixados = db.escalar(
            "SELECT count(*) FROM raw.ccee_pld_horario WHERE resource_id = :r", {"r": resource_id}
        )
        if ja_baixados >= total and not forcar:
            execucao.status = "CACHE"
            execucao.aviso(f"{ja_baixados} registros ja estavam no raw (total na API: {total}). Nada baixado.")
            return

        offset = 0 if forcar else ja_baixados
        tamanho = cfg["tamanho_pagina"]
        while offset < total:
            pagina = cliente.get_json(url, {"resource_id": resource_id, "limit": tamanho, "offset": offset, "sort": "_id asc"})
            registros = pagina.get("result", {}).get("records", [])
            if not registros:
                execucao.aviso(f"Pagina vazia no offset {offset} (total informado {total}). Paginacao encerrada.")
                break
            _validar_colunas(registros[0].keys(), cfg["colunas_esperadas"])
            linhas = [
                (resource_id, ano, int(r["_id"]), r, f"{url}?resource_id={resource_id}&offset={offset}", execucao.id)
                for r in registros
            ]
            gravadas = db.inserir_lote(
                "raw.ccee_pld_horario",
                ["resource_id", "ano_recurso", "id_registro", "registro", "url_origem", "id_execucao"],
                linhas,
                "ON CONFLICT (resource_id, id_registro) DO UPDATE SET registro = EXCLUDED.registro, extraido_em = now(), id_execucao = EXCLUDED.id_execucao",
            )
            execucao.linhas_lidas += len(registros)
            execucao.linhas_gravadas += gravadas
            offset += len(registros)
            log.info("PLD %s: %s/%s registros", ano, offset, total)

        if cliente.total_tentativas_extras:
            execucao.aviso(f"{cliente.total_tentativas_extras} novas tentativas HTTP foram necessarias")
        if offset < total:
            execucao.status = "PARCIAL"


def _parse_data(dia, mes_referencia=None):
    texto = str(dia).strip()
    if texto.isdigit() and len(texto) <= 2 and mes_referencia:
        try:
            ref = str(mes_referencia).strip()[:6]
            return datetime(int(ref[:4]), int(ref[4:6]), int(texto))
        except ValueError:
            return None
    texto = texto[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def _parse_numero(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("\r", "")
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def ler_raw_normalizado():
    raw = db.consultar("SELECT id_raw, resource_id, ano_recurso, extraido_em, registro FROM raw.ccee_pld_horario")
    if raw.empty:
        return pd.DataFrame()
    registros = pd.json_normalize(raw["registro"])
    registros.columns = [c.upper() for c in registros.columns]
    df = pd.concat([raw.drop(columns="registro").reset_index(drop=True), registros], axis=1)
    df["cod_submercado"] = df["SUBMERCADO"].astype(str).str.strip().str.upper().map(MAPA_SUBMERCADO)
    df["dia"] = [_parse_data(d, m) for d, m in zip(df["DIA"], df["MES_REFERENCIA"])]
    df["hora"] = pd.to_numeric(df["HORA"], errors="coerce")
    deslocamento = df.groupby("resource_id")["hora"].transform(lambda h: 1 if h.max() == 24 else 0)
    df["hora_ajustada"] = df["hora"] - deslocamento
    df["data_hora"] = pd.to_datetime(df["dia"]) + pd.to_timedelta(df["hora_ajustada"], unit="h")
    df["pld_rs_mwh"] = df["PLD_HORA"].map(_parse_numero)
    df["mes_referencia"] = df["MES_REFERENCIA"].astype(str).str.strip().str[:6]
    df["periodo_comercializacao"] = pd.to_numeric(df["PERIODO_COMERCIALIZACAO"], errors="coerce")
    return df


def transformar():
    with registrar("transformacao_pld", "raw.ccee_pld_horario") as execucao:
        df = ler_raw_normalizado()
        execucao.linhas_lidas = len(df)
        if df.empty:
            execucao.status = "SEM_DADOS"
            return
        invalidos = df[df[["cod_submercado", "data_hora", "pld_rs_mwh"]].isna().any(axis=1)]
        if len(invalidos):
            execucao.aviso(f"{len(invalidos)} registros do raw nao puderam ser convertidos (submercado, data ou valor invalido)")
        validos = df.drop(invalidos.index).sort_values("extraido_em")
        duplicados = validos.duplicated(["cod_submercado", "data_hora"], keep="last").sum()
        if duplicados:
            execucao.aviso(f"{duplicados} registros duplicados (submercado+hora) no raw; mantida a extracao mais recente")
        final = validos.drop_duplicates(["cod_submercado", "data_hora"], keep="last")
        saida = pd.DataFrame({
            "cod_submercado": final["cod_submercado"],
            "data_hora": final["data_hora"],
            "mes_referencia": final["mes_referencia"].fillna(final["data_hora"].dt.strftime("%Y%m")),
            "periodo_comercializacao": final["periodo_comercializacao"].fillna(0).astype(int),
            "pld_rs_mwh": final["pld_rs_mwh"].round(2),
            "resource_id": final["resource_id"],
            "id_raw": final["id_raw"],
        })
        db.executar("TRUNCATE tratado.pld_horario")
        execucao.linhas_gravadas = db.inserir_dataframe("tratado.pld_horario", saida)


def executar(forcar=False):
    cfg = config.ccee()
    cliente = _cliente()
    recursos = descobrir_recursos(cliente, cfg)
    for ano in cfg["anos"]:
        resource_id = recursos.get(ano)
        if not resource_id:
            with registrar("extracao_pld", "CCEE", {"ano": ano}) as execucao:
                execucao.status = "SEM_DADOS"
                execucao.aviso(f"Nenhum recurso do PLD horario encontrado para {ano}")
            continue
        extrair_ano(cliente, cfg, ano, resource_id, forcar)
    transformar()
