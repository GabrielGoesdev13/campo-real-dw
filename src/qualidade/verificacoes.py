import numpy as np
import pandas as pd


def nulos(df, colunas):
    return df[colunas].isna().any(axis=1)


def texto_vazio(df, colunas):
    mascara = pd.Series(False, index=df.index)
    for coluna in colunas:
        mascara |= df[coluna].isna() | (df[coluna].astype(str).str.strip() == "")
    return mascara


def duplicados(df, chave):
    return df.duplicated(chave, keep=False) & df[chave].notna().all(axis=1)


def fora_da_faixa(df, coluna, minimo=None, maximo=None):
    valores = pd.to_numeric(df[coluna], errors="coerce")
    mascara = pd.Series(False, index=df.index)
    if minimo is not None:
        mascara |= valores < minimo
    if maximo is not None:
        mascara |= valores > maximo
    return mascara & valores.notna()


def fora_do_padrao(df, coluna, regex):
    return ~df[coluna].astype(str).str.fullmatch(regex)


def sem_correspondencia(df, coluna, valores_validos):
    return ~df[coluna].isin(set(valores_validos))


def datas_invertidas(df, inicio, fim):
    return df[fim] < df[inicio]


def fora_do_periodo(df, coluna, inicio, fim):
    return (df[coluna] < pd.Timestamp(inicio)) | (df[coluna] > pd.Timestamp(fim))


def evento_antes_de(df, coluna_evento, coluna_referencia):
    return df[coluna_referencia] < df[coluna_evento]


def atraso_maior_que(df, coluna_evento, coluna_chegada, horas):
    return (df[coluna_chegada] - df[coluna_evento]) > pd.Timedelta(hours=horas)


def acima_do_limite(df, coluna, coluna_limite, fator=1.0):
    return pd.to_numeric(df[coluna], errors="coerce") > pd.to_numeric(df[coluna_limite], errors="coerce") * fator


def lacunas_horarias(df, grupo, coluna_tempo, inicio, fim, grupos_esperados=None):
    horas = pd.date_range(inicio, fim, freq="h")
    grupos = grupos_esperados if grupos_esperados is not None else df[grupo].dropna().unique()
    esperado = pd.MultiIndex.from_product([grupos, horas], names=[grupo, coluna_tempo]).to_frame(index=False)
    existentes = df[[grupo, coluna_tempo]].dropna().drop_duplicates()
    juncao = esperado.merge(existentes, how="left", indicator=True)
    return len(esperado), juncao[juncao["_merge"] == "left_only"].drop(columns="_merge")


def sequencia_constante(df, grupo, ordem, coluna, minimo, ignorar_zero=True):
    ordenado = df.sort_values([grupo, ordem])
    valores = ordenado[coluna]
    mudou = (valores != valores.shift()) | (ordenado[grupo] != ordenado[grupo].shift())
    bloco = mudou.cumsum()
    tamanho = bloco.map(bloco.value_counts())
    mascara = tamanho >= minimo
    if ignorar_zero:
        mascara &= valores.fillna(0) != 0
    mascara &= valores.notna()
    return mascara.reindex(df.index)


def dentro_de_intervalos(df, grupo, coluna_tempo, intervalos, grupo_intervalo, inicio, fim):
    mascara = pd.Series(False, index=df.index)
    for intervalo in intervalos.itertuples():
        mascara |= (
            (df[grupo] == getattr(intervalo, grupo_intervalo))
            & (df[coluna_tempo] >= getattr(intervalo, inicio))
            & (df[coluna_tempo] <= getattr(intervalo, fim))
        )
    return mascara


def intervalos_sobrepostos(df, grupo, inicio, fim):
    ordenado = df.sort_values([grupo, inicio])
    anterior_fim = ordenado.groupby(grupo)[fim].shift()
    return (ordenado[inicio] <= anterior_fim).reindex(df.index).fillna(False)


def ultimo_registro_antes(df, grupo, coluna_tempo, limite):
    ultimos = df.groupby(grupo)[coluna_tempo].max()
    return ultimos[ultimos < pd.Timestamp(limite)].reset_index()


def outlier_robusto(df, grupos, coluna, limite_z=6.0):
    valores = pd.to_numeric(df[coluna], errors="coerce")
    mediana = valores.groupby([df[g] for g in grupos]).transform("median")
    mad = (valores - mediana).abs().groupby([df[g] for g in grupos]).transform("median")
    z = 0.6745 * (valores - mediana) / mad.replace(0, np.nan)
    return z.abs() > limite_z


def coordenada_fora_da_uf(df, funcao_dentro):
    return ~df.apply(lambda r: funcao_dentro(r["uf"], r["latitude"], r["longitude"]), axis=1)
