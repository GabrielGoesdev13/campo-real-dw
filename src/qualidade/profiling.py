import pandas as pd

from src import db


def perfil(df, tabela):
    linhas = []
    total = len(df)
    for coluna in df.columns:
        serie = df[coluna]
        if serie.map(lambda x: isinstance(x, (dict, list))).any():
            continue
        numerica = pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)
        nao_nulos = serie.dropna()
        moda = nao_nulos.astype(str).mode()
        item = {
            "tabela": tabela,
            "coluna": coluna,
            "tipo": str(serie.dtype),
            "total": total,
            "nulos": int(serie.isna().sum()),
            "pct_nulos": round(100 * serie.isna().mean(), 3) if total else 0,
            "distintos": int(serie.nunique(dropna=True)),
            "minimo": str(nao_nulos.min()) if len(nao_nulos) and not pd.api.types.is_bool_dtype(serie) else None,
            "maximo": str(nao_nulos.max()) if len(nao_nulos) and not pd.api.types.is_bool_dtype(serie) else None,
            "media": None, "desvio": None, "p05": None, "p50": None, "p95": None,
            "mais_frequente": moda.iloc[0][:200] if len(moda) else None,
        }
        if numerica and len(nao_nulos):
            item.update({
                "media": float(nao_nulos.mean()),
                "desvio": float(nao_nulos.std()) if len(nao_nulos) > 1 else 0.0,
                "p05": float(nao_nulos.quantile(0.05)),
                "p50": float(nao_nulos.quantile(0.50)),
                "p95": float(nao_nulos.quantile(0.95)),
            })
        linhas.append(item)
    return pd.DataFrame(linhas)


def gravar(tabelas, id_execucao):
    partes = [perfil(df, nome) for nome, df in tabelas.items() if df is not None and not df.empty]
    if not partes:
        return 0
    resultado = pd.concat(partes, ignore_index=True)
    resultado.insert(0, "id_execucao", id_execucao)
    db.inserir_dataframe("qualidade.profiling", resultado)
    return len(resultado)
