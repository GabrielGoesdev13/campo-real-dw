import logging
from datetime import datetime

import pandas as pd

from src import config, db

log = logging.getLogger(__name__)

NOMES_INDICADOR = {
    "geracao_mwh": "Geração (MWh)",
    "receita_valorada_rs": "Receita valorada ao PLD (R$)",
    "preco_capturado_rs_mwh": "Preço capturado (R$/MWh)",
    "geracao_sem_usina_mwh": "Geração sem usina identificada (MWh)",
    "linhas_medicao": "Linhas de medição",
}


def _num(valor, casas=0):
    if valor is None or pd.isna(valor):
        return "-"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _tabela(df):
    if df.empty:
        return "_Sem registros._\n"
    cab = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    linhas = ["| " + " | ".join("" if pd.isna(v) else str(v).replace("|", "/").replace("\n", " ") for v in linha) + " |" for linha in df.values]
    return "\n".join([cab, sep, *linhas]) + "\n"


def _ultimas_metricas():
    return db.consultar(
        """SELECT m.cod_regra, m.dimensao, m.tabela, r.descricao, r.acao, r.justificativa,
                  m.registros_avaliados, m.registros_falha, m.percentual_falha, m.executado_em
             FROM qualidade.metrica m
             JOIN qualidade.regra r ON r.cod_regra = m.cod_regra
            WHERE m.id_execucao = (SELECT max(m2.id_execucao) FROM qualidade.metrica m2 WHERE m2.cod_regra = m.cod_regra)
            ORDER BY m.dimensao, m.cod_regra"""
    )


def gerar(caminho=None):
    caminho = caminho or config.PASTA_DOCS / "relatorio_qualidade.md"
    metricas = _ultimas_metricas()
    if metricas.empty:
        log.warning("Nenhuma metrica de qualidade encontrada; rode a etapa de qualidade antes")
        return
    exec_origem = db.escalar("SELECT max(id_execucao) FROM controle.log_execucao WHERE processo = 'qualidade_origem' AND status = 'SUCESSO'")
    exec_clima = db.escalar("SELECT max(id_execucao) FROM controle.log_execucao WHERE processo = 'qualidade_clima' AND status = 'SUCESSO'")
    execucoes = [e for e in [exec_origem, exec_clima] if e]
    quarentena = db.consultar(
        """SELECT q.tabela_origem AS tabela, q.cod_regra AS regra, count(*) AS registros, min(q.motivo) AS motivo
             FROM qualidade.quarentena q WHERE q.id_execucao = ANY(:e) GROUP BY 1, 2 ORDER BY 1, 2""",
        {"e": execucoes},
    )
    impacto = db.consultar(
        "SELECT indicador, recorte, antes, depois, diferenca, pct_variacao FROM qualidade.impacto_limpeza WHERE id_execucao = :e",
        {"e": exec_origem},
    )
    status = db.consultar("SELECT status_qualidade, count(*) AS linhas FROM tratado.medicao_geracao GROUP BY 1 ORDER BY 2 DESC")
    ocorrencias = db.consultar(
        """SELECT o.cod_regra, o.chave::text AS chave, o.detalhe::text AS detalhe
             FROM qualidade.ocorrencia o WHERE o.id_execucao = ANY(:e)""",
        {"e": execucoes},
    )
    perfil = db.consultar(
        """SELECT coluna, tipo, total, nulos, distintos, minimo, maximo, round(media, 3) AS media, round(p50, 3) AS mediana
             FROM qualidade.profiling WHERE id_execucao = :e AND tabela LIKE '%medicao_geracao' ORDER BY coluna""",
        {"e": exec_origem},
    )
    logs = db.consultar(
        """SELECT DISTINCT ON (processo, fonte) processo, fonte, status, linhas_lidas, linhas_gravadas,
                  to_char(inicio AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS inicio, left(coalesce(mensagem_erro, ''), 160) AS mensagem
             FROM controle.log_execucao ORDER BY processo, fonte, id_execucao DESC"""
    )

    dim = metricas.groupby("dimensao").agg(
        regras=("cod_regra", "count"),
        registros_avaliados=("registros_avaliados", "sum"),
        registros_com_falha=("registros_falha", "sum"),
        regras_com_falha=("registros_falha", lambda s: int((s > 0).sum())),
    ).reset_index()
    dim["indice_qualidade_%"] = (100 - 100 * dim["registros_com_falha"] / dim["registros_avaliados"]).round(3)
    dim = dim.sort_values("indice_qualidade_%")

    partes = []
    partes.append("# Relatório de Qualidade de Dados — Campo Real Energia\n\n")
    partes.append(f"_Gerado automaticamente por `run_pipeline.py --etapas relatorio` em {datetime.now():%d/%m/%Y %H:%M}. "
                  f"Fonte: tabelas `qualidade.metrica`, `qualidade.regra`, `qualidade.quarentena` e `qualidade.impacto_limpeza`._\n")

    total_av = int(metricas["registros_avaliados"].sum())
    total_falha = int(metricas["registros_falha"].sum())
    partes.append("## 1. Resumo\n\n")
    partes.append(f"- **{len(metricas)} regras** avaliadas, cobrindo as **7 dimensões** de qualidade.\n"
                  f"- **{_num(total_av)} verificações** de registro; **{_num(total_falha)} falhas** em **{int((metricas['registros_falha'] > 0).sum())} regras**.\n"
                  f"- **{int(quarentena['registros'].sum()) if not quarentena.empty else 0} registros em quarentena** (fora do caminho até o DW, guardados com o JSON original).\n")
    tot = impacto[impacto["recorte"] == "TOTAL"].set_index("indicador")
    if "geracao_mwh" in tot.index:
        partes.append(f"- Geração 2025: **{_num(tot.loc['geracao_mwh', 'antes'])} MWh antes** × **{_num(tot.loc['geracao_mwh', 'depois'])} MWh depois** "
                      f"({_num(tot.loc['geracao_mwh', 'pct_variacao'], 2)}%).\n")
    if "receita_valorada_rs" in tot.index and pd.notna(tot.loc["receita_valorada_rs", "antes"]):
        partes.append(f"- Receita valorada ao PLD: **R$ {_num(tot.loc['receita_valorada_rs', 'antes'] / 1e6, 2)} mi antes** × "
                      f"**R$ {_num(tot.loc['receita_valorada_rs', 'depois'] / 1e6, 2)} mi depois** ({_num(tot.loc['receita_valorada_rs', 'pct_variacao'], 2)}%).\n")
    partes.append("\n")

    partes.append("## 2. Índice de qualidade por dimensão\n\n")
    partes.append("Índice = 100% − (registros com falha ÷ registros avaliados). Um mesmo registro pode falhar em mais de uma regra.\n\n")
    d = dim.copy()
    for c in ["registros_avaliados", "registros_com_falha"]:
        d[c] = d[c].map(_num)
    d["indice_qualidade_%"] = d["indice_qualidade_%"].map(lambda x: _num(x, 3))
    partes.append(_tabela(d.rename(columns={"dimensao": "Dimensão", "regras": "Regras", "registros_avaliados": "Avaliados",
                                            "registros_com_falha": "Falhas", "regras_com_falha": "Regras com falha",
                                            "indice_qualidade_%": "Índice (%)"})))

    partes.append("\n## 3. Problemas encontrados, decisão e justificativa\n\n")
    partes.append("Ações possíveis: **CORRIGIR** (valor alterado, original preservado), **DESCARTAR** (cópia removida), "
                  "**QUARENTENA** (retirado e guardado para auditoria), **SINALIZAR** (mantido e marcado), **COMPLEMENTAR** (dado de referência acrescentado).\n")
    com_falha = metricas[metricas["registros_falha"] > 0]
    for dimensao, grupo in com_falha.groupby("dimensao"):
        partes.append(f"\n### {dimensao}\n\n")
        for r in grupo.itertuples():
            partes.append(f"\n**{r.cod_regra} — {r.descricao}**  \n"
                          f"Tabela: `{r.tabela}` · Afetados: **{_num(r.registros_falha)}** de {_num(r.registros_avaliados)} "
                          f"({_num(r.percentual_falha, 3)}%) · Decisão: **{r.acao}**  \n"
                          f"Justificativa: {r.justificativa}\n")
            exemplos = ocorrencias[ocorrencias["cod_regra"] == r.cod_regra].head(3)
            if not exemplos.empty:
                partes.append("Exemplos: " + "; ".join(f"`{c}`" for c in exemplos["chave"]) + "\n")

    sem = metricas[metricas["registros_falha"] == 0]
    partes.append("\n## 4. Regras executadas sem ocorrência\n\n")
    partes.append("Estas regras rodam em toda carga e protegem contra problemas que não apareceram nesta execução.\n\n")
    partes.append(_tabela(sem[["cod_regra", "dimensao", "tabela", "descricao"]].rename(
        columns={"cod_regra": "Regra", "dimensao": "Dimensão", "tabela": "Tabela", "descricao": "Descrição"})))

    partes.append("\n## 5. Quarentena\n\n")
    partes.append(_tabela(quarentena.rename(columns={"tabela": "Tabela", "regra": "Regra", "registros": "Registros", "motivo": "Motivo"})))

    partes.append("\n## 6. Impacto da limpeza nos indicadores de negócio (antes × depois)\n\n")
    partes.append("**Antes** = soma ingênua da tabela de origem (como um analista faria sem tratar nada). "
                  "**Depois** = dado tratado que alimenta o DW (sem medições de usina desconhecida).\n\n")
    imp = impacto[impacto["recorte"].str.match(r"^(TOTAL|FONTE)")].copy()
    imp["indicador"] = imp["indicador"].map(lambda x: NOMES_INDICADOR.get(x, x))
    imp["recorte"] = imp["recorte"].str.replace("FONTE:", "Fonte ", regex=False)
    imp["antes"] = imp["antes"].map(lambda x: _num(x, 2))
    imp["depois"] = imp["depois"].map(lambda x: _num(x, 2))
    imp["diferenca"] = imp["diferenca"].map(lambda x: _num(x, 2))
    imp["pct_variacao"] = imp["pct_variacao"].map(lambda x: _num(x, 2))
    partes.append(_tabela(imp.rename(columns={"indicador": "Indicador", "recorte": "Recorte", "antes": "Antes", "depois": "Depois",
                                              "diferenca": "Diferença", "pct_variacao": "Variação (%)"})))

    partes.append("\n## 7. Situação das medições após a limpeza\n\n")
    partes.append(_tabela(status.rename(columns={"status_qualidade": "Status", "linhas": "Linhas"})))

    partes.append("\n## 8. Profiling da tabela de medição (origem)\n\n")
    partes.append("O profiling completo de todas as tabelas está em `qualidade.profiling`.\n\n")
    partes.append(_tabela(perfil))

    partes.append("\n## 9. Últimas execuções do pipeline (controle.log_execucao)\n\n")
    partes.append(_tabela(logs))

    caminho.write_text("".join(partes), encoding="utf-8")
    log.info("Relatorio gerado em %s", caminho)
