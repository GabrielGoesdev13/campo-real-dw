import pandas as pd

from src import db


def _indicadores(medicao, pld, usina, fonte):
    base = medicao.merge(usina[["id_usina", "cod_usina", "cod_submercado", "id_fonte"]], on="id_usina", how="left")
    base = base.merge(fonte[["id_fonte", "cod_fonte"]], on="id_fonte", how="left")
    base = base.merge(pld[["cod_submercado", "data_hora", "pld_rs_mwh"]], on=["cod_submercado", "data_hora"], how="left")
    base["receita_rs"] = base["energia_mwh"] * base["pld_rs_mwh"]
    base["com_preco"] = base["pld_rs_mwh"].notna() & base["energia_mwh"].notna()
    resultado = []

    def adicionar(indicador, recorte, valor):
        resultado.append({"indicador": indicador, "recorte": recorte, "valor": float(valor) if pd.notna(valor) else None})

    adicionar("geracao_mwh", "TOTAL", base["energia_mwh"].sum())
    adicionar("geracao_sem_usina_mwh", "TOTAL", base.loc[base["cod_usina"].isna(), "energia_mwh"].sum())
    adicionar("receita_valorada_rs", "TOTAL", base["receita_rs"].sum())
    valorada = base[base["com_preco"]]
    adicionar("preco_capturado_rs_mwh", "TOTAL", valorada["receita_rs"].sum() / valorada["energia_mwh"].sum())
    adicionar("linhas_medicao", "TOTAL", len(base))
    for chave, nome in [("cod_fonte", "FONTE"), ("cod_usina", "USINA")]:
        for valor, grupo in base.dropna(subset=[chave]).groupby(chave):
            adicionar("geracao_mwh", f"{nome}:{valor}", grupo["energia_mwh"].sum())
            adicionar("receita_valorada_rs", f"{nome}:{valor}", grupo["receita_rs"].sum())
            g = grupo[grupo["com_preco"]]
            if g["energia_mwh"].sum():
                adicionar("preco_capturado_rs_mwh", f"{nome}:{valor}", g["receita_rs"].sum() / g["energia_mwh"].sum())
    return pd.DataFrame(resultado)


def calcular(medicao_bruta, usina_bruta, fonte, pld_bruto, medicao_limpa, usina_limpa, pld_limpo, id_execucao):
    antes = _indicadores(medicao_bruta, pld_bruto, usina_bruta, fonte)
    limpa = medicao_limpa[medicao_limpa["status_qualidade"] != "DESCONHECIDA"]
    depois = _indicadores(limpa, pld_limpo, usina_limpa, fonte)
    desconhecida = medicao_limpa.loc[medicao_limpa["status_qualidade"] == "DESCONHECIDA", "energia_mwh"].sum()
    depois.loc[(depois["indicador"] == "geracao_sem_usina_mwh"), "valor"] = desconhecida
    tabela = antes.merge(depois, on=["indicador", "recorte"], how="outer", suffixes=("_antes", "_depois"))
    tabela = tabela.rename(columns={"valor_antes": "antes", "valor_depois": "depois"})
    tabela["diferenca"] = tabela["depois"] - tabela["antes"]
    tabela["pct_variacao"] = (100 * tabela["diferenca"] / tabela["antes"].where(tabela["antes"] != 0)).round(4)
    tabela.insert(0, "id_execucao", id_execucao)
    db.inserir_dataframe("qualidade.impacto_limpeza", tabela[["id_execucao", "indicador", "recorte", "antes", "depois", "diferenca", "pct_variacao"]])
    return tabela
