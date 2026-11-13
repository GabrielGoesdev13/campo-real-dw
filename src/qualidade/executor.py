import logging

import pandas as pd

from src import config, db, referencias
from src.extracao import pld_ccee
from src.log_execucao import registrar
from src.qualidade import impacto, limpeza, profiling
from src.qualidade.regras import por_escopo, REGRAS

log = logging.getLogger(__name__)
O = config.SCHEMA_ORIGEM
MAX_OCORRENCIAS = 5000
CHAVES = ["id_medicao", "id_usina", "cod_usina", "id_parada", "id_raw", "cod_submercado", "data_hora", "data", "ano", "id_fonte", "ultimo_mes"]


def _datas(df, colunas):
    for coluna in colunas:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna])
    return df


def _aparar(df, colunas=("cod_submercado", "uf", "cod_fonte", "mes_referencia")):
    for coluna in colunas:
        if coluna in df.columns:
            df[coluna] = df[coluna].where(df[coluna].isna(), df[coluna].astype(str).str.rstrip())
    return df


def carregar_origem():
    usina = _aparar(db.consultar(f"SELECT * FROM {O}.usina ORDER BY id_usina"))
    fonte = _aparar(db.consultar(f"SELECT * FROM {O}.fonte_energia ORDER BY id_fonte"))
    submercado = _aparar(db.consultar(f"SELECT * FROM {O}.submercado"))
    feriado = db.consultar(f"SELECT * FROM {O}.feriado_nacional ORDER BY data")
    parada = _datas(db.consultar(f"SELECT * FROM {O}.parada_usina ORDER BY id_parada"), ["inicio", "fim"])
    medicao = _datas(db.consultar(f"SELECT * FROM {O}.medicao_geracao ORDER BY id_medicao"), ["data_hora", "recebido_em"])
    pld = _aparar(_datas(db.consultar("SELECT * FROM tratado.pld_horario"), ["data_hora"]))
    return usina, fonte, submercado, feriado, parada, medicao, pld


def montar_contexto(usina, fonte, submercado, feriado, parada, medicao, pld, pld_raw):
    info = usina.merge(fonte[["id_fonte", "cod_fonte"]], on="id_fonte", how="left")
    med = medicao.merge(info[["id_usina", "cod_usina", "cod_submercado", "potencia_mw", "cod_fonte"]], on="id_usina", how="left")
    med.index = medicao.index
    canon = limpeza.usinas_canonicas(usina)
    return {
        "usina": usina, "fonte": fonte, "submercado": submercado, "feriado": feriado, "parada": parada,
        "medicao": med, "pld": pld, "pld_raw": pld_raw, "municipios": referencias.municipios(),
        "usinas_canonicas": canon.loc[canon["id_usina"] == canon["id_canonico"], "id_usina"].tolist(),
    }


def salvar_catalogo():
    catalogo = pd.DataFrame([
        {"cod_regra": r.codigo, "dimensao": r.dimensao, "tabela": r.tabela, "descricao": r.descricao,
         "acao": r.acao, "justificativa": r.justificativa} for r in REGRAS
    ])
    db.inserir_dataframe(
        "qualidade.regra", catalogo,
        """ON CONFLICT (cod_regra) DO UPDATE SET dimensao = EXCLUDED.dimensao, tabela = EXCLUDED.tabela,
           descricao = EXCLUDED.descricao, acao = EXCLUDED.acao, justificativa = EXCLUDED.justificativa""",
    )


def avaliar(escopo, ctx, id_execucao):
    metricas, ocorrencias = [], []
    for r in por_escopo(escopo):
        avaliados, falhas = r.funcao(ctx)
        qtd = len(falhas)
        pct = round(100 * qtd / avaliados, 3) if avaliados else 0.0
        metricas.append((id_execucao, r.codigo, r.dimensao, r.tabela, int(avaliados), int(qtd), pct))
        log.info("%-8s %-24s %-28s avaliados=%-7s falhas=%-6s (%.3f%%)", r.codigo, r.dimensao, r.tabela, avaliados, qtd, pct)
        if qtd:
            chaves = [c for c in CHAVES if c in falhas.columns] or list(falhas.columns)
            for registro in falhas.head(MAX_OCORRENCIAS).to_dict("records"):
                chave = {k: _serializavel(registro.get(k)) for k in chaves}
                detalhe = {k: _serializavel(x) for k, x in registro.items() if k not in chaves and not isinstance(x, (list, dict))}
                ocorrencias.append((id_execucao, r.codigo, r.tabela, chave, detalhe))
    db.inserir_lote("qualidade.metrica", ["id_execucao", "cod_regra", "dimensao", "tabela", "registros_avaliados", "registros_falha", "percentual_falha"], metricas)
    db.inserir_lote("qualidade.ocorrencia", ["id_execucao", "cod_regra", "tabela", "chave", "detalhe"], ocorrencias)
    return metricas


def _serializavel(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if valor is pd.NaT:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    if hasattr(valor, "item"):
        valor = valor.item()
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


def _gravar_quarentena(quarentena, id_execucao):
    linhas = [(id_execucao, tabela, regra, registro, motivo) for tabela, regra, registro, motivo in quarentena.itens]
    db.inserir_lote("qualidade.quarentena", ["id_execucao", "tabela_origem", "cod_regra", "registro", "motivo"], linhas)
    return len(linhas)


def executar_origem():
    with registrar("qualidade_origem", f"{O} + tratado.pld_horario", propagar_erro=True) as execucao:
        usina, fonte, submercado, feriado, parada, medicao, pld = carregar_origem()
        pld_raw = pld_ccee.ler_raw_normalizado()
        execucao.linhas_lidas = sum(len(t) for t in [usina, fonte, submercado, feriado, parada, medicao, pld])
        if pld.empty:
            execucao.aviso("tratado.pld_horario esta vazia: a receita valorada nao podera ser calculada")

        profiling.gravar({
            f"{O}.usina": usina, f"{O}.fonte_energia": fonte, f"{O}.submercado": submercado,
            f"{O}.feriado_nacional": feriado, f"{O}.parada_usina": parada, f"{O}.medicao_geracao": medicao,
            "tratado.pld_horario": pld,
        }, execucao.id)

        salvar_catalogo()
        ctx = montar_contexto(usina, fonte, submercado, feriado, parada, medicao, pld, pld_raw)
        avaliar("origem", ctx, execucao.id)

        quarentena = limpeza.Quarentena()
        usina_t, mapa, duplicadas = limpeza.limpar_usina(usina, medicao, quarentena)
        parada_t = limpeza.limpar_parada(parada, mapa, quarentena)
        anos = set(pld["data_hora"].dt.year.dropna().astype(int)) | {pd.Timestamp(config.qualidade()["periodo_inicio"]).year}
        feriado_t = limpeza.limpar_feriado(feriado, anos)
        medicao_t = limpeza.limpar_medicao(medicao, usina_t, mapa, parada_t, fonte, quarentena)
        pld_t, _ = limpeza.limpar_pld(pld, pld_raw, quarentena)

        for tabela in ["medicao_geracao", "parada_usina", "feriado", "mapa_usina", "usina", "fonte_energia", "submercado"]:
            db.executar(f"TRUNCATE tratado.{tabela}")
        db.inserir_dataframe("tratado.submercado", submercado.assign(cod_submercado=submercado["cod_submercado"].str.strip())[["cod_submercado", "nome", "regioes"]])
        db.inserir_dataframe("tratado.fonte_energia", fonte[["id_fonte", "cod_fonte", "descricao", "renovavel", "intermitente"]])
        db.inserir_dataframe("tratado.usina", usina_t)
        db.inserir_dataframe("tratado.mapa_usina", mapa)
        db.inserir_dataframe("tratado.feriado", feriado_t)
        db.inserir_dataframe("tratado.parada_usina", parada_t)
        gravadas = db.inserir_dataframe("tratado.medicao_geracao", medicao_t)
        removidos_pld = len(pld) - len(pld_t)
        if removidos_pld:
            db.executar("DELETE FROM tratado.pld_horario t USING qualidade.quarentena q WHERE q.id_execucao = :e AND q.cod_regra = 'PLD-V01' AND t.cod_submercado = q.registro->>'cod_submercado' AND t.data_hora = (q.registro->>'data_hora')::timestamp", {"e": execucao.id})

        em_quarentena = _gravar_quarentena(quarentena, execucao.id)
        execucao.linhas_gravadas = gravadas + len(usina_t) + len(parada_t) + len(feriado_t)
        execucao.aviso(f"{em_quarentena} registros em quarentena; {len(duplicadas)} usina(s) duplicada(s) mapeada(s)")

        resumo = medicao_t["status_qualidade"].value_counts().to_dict()
        log.info("Status das medicoes tratadas: %s", resumo)
        impacto.calcular(medicao, usina, fonte, pld, medicao_t, usina_t, pld_t, execucao.id)


def executar_clima():
    with registrar("qualidade_clima", "tratado.clima_horario", propagar_erro=True) as execucao:
        clima = _datas(db.consultar("SELECT * FROM tratado.clima_horario"), ["data_hora"])
        usina_t = _aparar(db.consultar("SELECT * FROM tratado.usina"))
        execucao.linhas_lidas = len(clima)
        if clima.empty:
            execucao.status = "SEM_DADOS"
            execucao.aviso("Sem dados de clima para avaliar")
            return
        profiling.gravar({"tratado.clima_horario": clima}, execucao.id)
        salvar_catalogo()
        avaliar("clima", {"clima": clima, "usina": usina_t}, execucao.id)
        quarentena = limpeza.Quarentena()
        limpo = limpeza.limpar_clima(clima, usina_t, quarentena)
        db.executar("TRUNCATE tratado.clima_horario")
        execucao.linhas_gravadas = db.inserir_dataframe("tratado.clima_horario", limpo.drop(columns=["carregado_em"], errors="ignore"))
        _gravar_quarentena(quarentena, execucao.id)


def executar(escopo):
    if escopo == "origem":
        executar_origem()
    elif escopo == "clima":
        executar_clima()
    else:
        raise ValueError(escopo)
