import numpy as np
import pandas as pd

from src import config, referencias
from src.qualidade import verificacoes as v

PRIORIDADE = ["ESTIMADO", "CORRIGIDO", "DESCONHECIDA", "SINALIZADO", "OK"]


class Quarentena:
    def __init__(self):
        self.itens = []

    def adicionar(self, df, tabela, regra, motivo):
        for registro in df.to_dict("records"):
            limpo = {k: (None if (not isinstance(x, (list, dict)) and pd.isna(x)) else (str(x) if isinstance(x, (pd.Timestamp,)) or hasattr(x, "isoformat") else x)) for k, x in registro.items()}
            self.itens.append((tabela, regra, limpo, motivo))


def usinas_canonicas(usina):
    u = usina.copy()
    u["nome_norm"] = u["nome"].str.strip().str.upper()
    u["padrao"] = u["cod_usina"].str.fullmatch(r"CRE-[A-Z]{3}-\d{3}")
    u = u.sort_values(["padrao", "id_usina"], ascending=[False, True])
    chave = ["nome_norm", "id_fonte", "latitude", "longitude", "potencia_mw"]
    u["id_canonico"] = u.groupby(chave)["id_usina"].transform("first")
    return u.sort_values("id_usina")


def limpar_usina(usina, medicao, quarentena):
    u = usinas_canonicas(usina)
    mapa = u[["id_usina", "id_canonico"]].rename(columns={"id_usina": "id_usina_origem", "id_canonico": "id_usina"})
    mapa["motivo"] = np.where(mapa["id_usina_origem"] == mapa["id_usina"], "id original", "USI-U01: cadastro duplicado")
    duplicadas = u[u["id_usina"] != u["id_canonico"]]
    u = u[u["id_usina"] == u["id_canonico"]].copy()
    u["flags"] = [[] for _ in range(len(u))]

    referencia = referencias.municipios().set_index("municipio")["uf"]
    for i, r in u.iterrows():
        uf_ref = referencia.get(r["municipio"])
        if uf_ref and uf_ref != r["uf"] and referencias.UF_SUBMERCADO.get(uf_ref) == r["cod_submercado"]:
            u.at[i, "uf"] = uf_ref
            u.at[i, "flags"].append(f"USI-K02: UF {r['uf']}->{uf_ref}")

    for i, r in u.iterrows():
        if not referencias.dentro_da_uf(r["uf"], r["latitude"], r["longitude"]):
            if referencias.dentro_da_uf(r["uf"], -r["latitude"], r["longitude"]):
                u.at[i, "latitude"] = -r["latitude"]
                u.at[i, "flags"].append(f"USI-K01: latitude {r['latitude']}->{-r['latitude']}")
            elif referencias.dentro_da_uf(r["uf"], r["latitude"], -r["longitude"]):
                u.at[i, "longitude"] = -r["longitude"]
                u.at[i, "flags"].append(f"USI-K01: longitude {r['longitude']}->{-r['longitude']}")

    inicio_periodo = config.qualidade()["periodo_inicio"]
    primeira = medicao[medicao["data_hora"] >= pd.Timestamp(inicio_periodo)].groupby("id_usina")["data_hora"].min()
    for i, r in u.iterrows():
        data = pd.Timestamp(r["data_inicio_operacao"]) if pd.notna(r["data_inicio_operacao"]) else None
        if data is not None and (data > pd.Timestamp.today() or (r["id_usina"] in primeira and data > primeira[r["id_usina"]])):
            u.at[i, "data_inicio_operacao"] = None
            u.at[i, "flags"].append(f"USI-V02: data_inicio_operacao {data.date()} anulada")

    u["flag_qualidade"] = u["flags"].map(lambda f: "; ".join(f)[:200] or None)
    colunas = ["id_usina", "cod_usina", "nome", "id_fonte", "cod_submercado", "uf", "municipio", "latitude", "longitude",
               "potencia_mw", "data_inicio_operacao", "situacao", "flag_qualidade"]
    u["nome"] = u["nome"].str.strip()
    return u[colunas], mapa, duplicadas


def limpar_parada(parada, usina, quarentena):
    invertidas = v.datas_invertidas(parada, "inicio", "fim")
    quarentena.adicionar(parada[invertidas], "parada_usina", "PAR-V01", "fim anterior ao inicio")
    sem_usina = v.sem_correspondencia(parada, "id_usina", usina["id_usina_origem"])
    quarentena.adicionar(parada[sem_usina & ~invertidas], "parada_usina", "PAR-I01", "usina inexistente")
    p = parada[~invertidas & ~sem_usina].copy()
    p["id_usina"] = p["id_usina"].map(usina.set_index("id_usina_origem")["id_usina"])
    return p[["id_parada", "id_usina", "inicio", "fim", "tipo", "motivo"]]


def limpar_feriado(feriado, anos):
    f = feriado.copy()
    f["data"] = pd.to_datetime(f["data"])
    f["origem"] = "ORIGEM"
    cobertos = set(f["data"].dt.year)
    novos = []
    for ano in sorted(anos):
        if ano not in cobertos:
            calc = referencias.feriados_nacionais(ano)
            calc["data"] = pd.to_datetime(calc["data"])
            calc["origem"] = "CALCULADO"
            novos.append(calc)
    if novos:
        f = pd.concat([f, *novos], ignore_index=True)
    f["data"] = f["data"].dt.date
    return f[["data", "descricao", "tipo", "origem"]]


def _interpolar_lacunas(serie, maximo):
    nulos = serie.isna()
    if not nulos.any():
        return serie, pd.Series(False, index=serie.index)
    bloco = (nulos != nulos.shift()).cumsum()
    tamanho = nulos.groupby(bloco).transform("sum")
    interpolada = serie.interpolate(method="linear", limit_area="inside")
    preencher = nulos & (tamanho <= maximo) & interpolada.notna()
    resultado = serie.where(~preencher, interpolada)
    return resultado, preencher


def limpar_medicao(medicao, usina_t, mapa, parada_t, fonte, quarentena):
    q = config.qualidade()
    m = medicao.copy()
    m["regras"] = [[] for _ in range(len(m))]
    m["status"] = "OK"
    m["energia_original_mwh"] = m["energia_mwh"]

    def marcar(mascara, regra, status):
        for i in m.index[mascara.reindex(m.index).fillna(False)]:
            m.at[i, "regras"].append(regra)
            if PRIORIDADE.index(status) < PRIORIDADE.index(m.at[i, "status"]):
                m.at[i, "status"] = status

    fora = v.fora_do_periodo(m, "data_hora", q["periodo_inicio"], q["periodo_fim"]) | m["data_hora"].isna()
    quarentena.adicionar(m.loc[fora, medicao.columns], "medicao_geracao", "MED-V02", "data fora do periodo de 2025")
    m = m[~fora]

    scada = m[m["origem"] == "SCADA"][["id_usina", "data_hora"]].drop_duplicates().assign(tem_scada=True)
    m = m.merge(scada, on=["id_usina", "data_hora"], how="left").set_index(m.index)
    conflito = (m["origem"] != "SCADA") & m["tem_scada"].fillna(False).astype(bool)
    quarentena.adicionar(m.loc[conflito, medicao.columns], "medicao_geracao", "MED-U02", "lancamento manual sobre leitura SCADA")
    m = m[~conflito].drop(columns="tem_scada")

    copia = m.sort_values("recebido_em").duplicated(["id_usina", "data_hora", "origem"], keep="first").reindex(m.index)
    m = m[~copia]

    m["id_usina"] = m["id_usina"].map(mapa.set_index("id_usina_origem")["id_usina"]).where(m["id_usina"].isin(mapa["id_usina_origem"]), m["id_usina"])
    info = usina_t.merge(fonte[["id_fonte", "cod_fonte"]], on="id_fonte", how="left")
    m = m.drop(columns=[c for c in ["potencia_mw", "cod_fonte", "cod_submercado", "cod_usina"] if c in m.columns])
    m = m.merge(info[["id_usina", "potencia_mw", "cod_submercado", "cod_usina", "cod_fonte"]], on="id_usina", how="left").set_index(m.index)
    m = m.sort_values(["id_usina", "data_hora"])

    desconhecida = m["cod_usina"].isna()
    marcar(desconhecida, "MED-I01", "DESCONHECIDA")

    kwh = v.acima_do_limite(m, "energia_mwh", "potencia_mw", 100)
    m.loc[kwh, "energia_mwh"] = (m.loc[kwh, "energia_mwh"] / 1000).round(3)
    marcar(kwh, "MED-A01", "CORRIGIDO")

    anterior = m.groupby("id_usina")["energia_mwh"].shift(1)
    posterior = m.groupby("id_usina")["energia_mwh"].shift(-1)
    vizinhos = pd.concat([anterior, posterior], axis=1).mean(axis=1)
    acima = v.acima_do_limite(m, "energia_mwh", "potencia_mw", 1)
    virgula = acima & ((m["energia_mwh"] / 10 - vizinhos).abs() <= 0.3 * vizinhos.clip(lower=1))
    pico = acima & ~virgula
    m.loc[virgula, "energia_mwh"] = (m.loc[virgula, "energia_mwh"] / 10).round(3)
    marcar(virgula, "MED-A02", "CORRIGIDO")
    m.loc[pico, "energia_mwh"] = vizinhos[pico].round(3)
    marcar(pico, "MED-A02", "ESTIMADO")

    negativa = v.fora_da_faixa(m, "energia_mwh", minimo=0)
    m.loc[negativa, "energia_mwh"] = 0.0
    marcar(negativa, "MED-V01", "CORRIGIDO")

    hora = m["data_hora"].dt.hour
    noite = (m["cod_fonte"] == "UFV") & ((hora >= 19) | (hora <= 5)) & (m["energia_mwh"] > 0)
    m.loc[noite, "energia_mwh"] = 0.0
    marcar(noite, "MED-K01", "CORRIGIDO")

    em_parada = v.dentro_de_intervalos(m, "id_usina", "data_hora", parada_t, "id_usina", "inicio", "fim") & (m["energia_mwh"] > 0)
    m.loc[em_parada, "energia_mwh"] = 0.0
    marcar(em_parada, "MED-K02", "CORRIGIDO")

    nulas = m["energia_mwh"].isna() & ~desconhecida
    estimadas = pd.Series(False, index=m.index)
    for _, grupo in m[~desconhecida].groupby("id_usina"):
        serie = grupo.set_index("data_hora")["energia_mwh"]
        preenchida, mascara = _interpolar_lacunas(serie, q["lacuna_maxima_interpolacao"])
        m.loc[grupo.index, "energia_mwh"] = preenchida.round(3).values
        estimadas.loc[grupo.index] = mascara.values
    marcar(estimadas & nulas, "MED-C01", "ESTIMADO")

    travado = v.sequencia_constante(m, "id_usina", "data_hora", "energia_original_mwh", q["horas_sensor_travado"])
    marcar(travado, "MED-A03", "SINALIZADO")
    marcar(v.atraso_maior_que(m, "data_hora", "recebido_em", q["atraso_maximo_horas"]), "MED-T01", "SINALIZADO")
    marcar(v.evento_antes_de(m, "data_hora", "recebido_em"), "MED-V03", "SINALIZADO")

    m["regras_aplicadas"] = m["regras"].map(lambda r: ", ".join(dict.fromkeys(r))[:200] or None)
    m["status_qualidade"] = m["status"]
    colunas = ["id_medicao", "id_usina", "data_hora", "energia_mwh", "energia_original_mwh", "disponibilidade_mw",
               "origem", "recebido_em", "status_qualidade", "regras_aplicadas"]
    return m[colunas].sort_values("id_medicao")


def limpar_pld(pld, pld_raw, quarentena):
    limites = config.limites_pld()
    piso = pld["data_hora"].dt.year.map(lambda a: limites.get(a, (None, None))[0])
    teto = pld["data_hora"].dt.year.map(lambda a: limites.get(a, (None, None))[1])
    fora = ((pld["pld_rs_mwh"] < piso - 0.01) | (pld["pld_rs_mwh"] > teto + 0.01)) & piso.notna()
    quarentena.adicionar(pld[fora], "pld_horario", "PLD-V01", "PLD fora do piso/teto ANEEL do ano")
    if not pld_raw.empty:
        invalidos = pld_raw[pld_raw[["cod_submercado", "data_hora", "pld_rs_mwh"]].isna().any(axis=1)]
        quarentena.adicionar(invalidos[["id_raw", "resource_id", "SUBMERCADO", "DIA", "HORA", "PLD_HORA"]], "ccee_pld_horario", "PLD-V02", "registro nao conversivel")
    return pld[~fora], pld[fora]


def limpar_clima(clima, usina_t, quarentena):
    c = clima.copy()
    sem_usina = v.sem_correspondencia(c, "cod_usina", usina_t["cod_usina"])
    quarentena.adicionar(c[sem_usina], "clima_horario", "CLI-I01", "ponto sem usina")
    c = c[~sem_usina].drop_duplicates(["cod_usina", "data_hora"])
    for coluna, minimo, maximo in [("radiacao_w_m2", 0, 1400), ("vento_100m_ms", 0, 60), ("temperatura_c", -10, 50)]:
        c.loc[v.fora_da_faixa(c, coluna, minimo, maximo), coluna] = None
    return c
