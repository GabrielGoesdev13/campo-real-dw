from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src import config, referencias
from src.qualidade import verificacoes as v

COMPLETUDE = "Completude"
UNICIDADE = "Unicidade"
VALIDADE = "Validade"
CONSISTENCIA = "Consistência"
ACURACIA = "Acurácia"
INTEGRIDADE = "Integridade referencial"
ATUALIDADE = "Atualidade"

O = config.SCHEMA_ORIGEM
T_MED = f"{O}.medicao_geracao"
T_USI = f"{O}.usina"
T_PAR = f"{O}.parada_usina"
T_FER = f"{O}.feriado_nacional"
T_SUB = f"{O}.submercado"
T_FON = f"{O}.fonte_energia"
T_PLD = "tratado.pld_horario"
T_PLD_RAW = "raw.ccee_pld_horario"
T_CLI = "tratado.clima_horario"


@dataclass
class Regra:
    codigo: str
    dimensao: str
    tabela: str
    descricao: str
    acao: str
    justificativa: str
    escopo: str
    funcao: Callable


REGRAS = []


def regra(codigo, dimensao, tabela, descricao, acao, justificativa, escopo="origem"):
    def registrar(funcao):
        REGRAS.append(Regra(codigo, dimensao, tabela, descricao, acao, justificativa, escopo, funcao))
        return funcao
    return registrar


def _filtro(df, mascara):
    return len(df), df[mascara.fillna(False)]


def _periodo():
    q = config.qualidade()
    return q["periodo_inicio"], q["periodo_fim"]


def _medicao_valida_no_periodo(ctx):
    med = ctx["medicao"]
    inicio, fim = _periodo()
    return med[~v.fora_do_periodo(med, "data_hora", inicio, fim) & med["data_hora"].notna()]


@regra("USI-C01", COMPLETUDE, T_USI, "Campos de cadastro da usina vazios (nome, município, UF, coordenadas, potência)",
       "SINALIZAR", "Campo vazio no cadastro não pode ser preenchido sem fonte. O único caso é o cadastro duplicado (USI-U01), que é descartado; os demais seriam apenas sinalizados.")
def usi_c01(ctx):
    u = ctx["usina"]
    return _filtro(u, v.texto_vazio(u, ["nome", "municipio", "uf"]) | v.nulos(u, ["latitude", "longitude", "potencia_mw"]))


@regra("USI-U01", UNICIDADE, T_USI, "Mesma usina cadastrada mais de uma vez (nome normalizado, fonte, coordenadas e potência iguais)",
       "DESCARTAR", "A segunda linha é uma cópia feita às pressas (código fora do padrão, nome com espaço extra, município vazio). Mantém-se o cadastro original e o id duplicado é mapeado para ele em tratado.mapa_usina, para nenhuma medição se perder.")
def usi_u01(ctx):
    u = ctx["usina"].copy()
    u["nome_norm"] = u["nome"].str.strip().str.upper()
    return _filtro(u, v.duplicados(u, ["nome_norm", "id_fonte", "latitude", "longitude", "potencia_mw"]))


@regra("USI-V01", VALIDADE, T_USI, "Código da usina fora do padrão CRE-XXX-999",
       "DESCARTAR", "O código é a chave de negócio usada no DW; um código fora do padrão indica cadastro irregular (é a mesma linha duplicada de USI-U01).")
def usi_v01(ctx):
    u = ctx["usina"]
    return _filtro(u, v.fora_do_padrao(u, "cod_usina", r"CRE-[A-Z]{3}-\d{3}"))


@regra("USI-V02", VALIDADE, T_USI, "Data de início de operação no futuro ou posterior à primeira medição",
       "CORRIGIR", "Uma usina não gera antes de começar a operar. A data verdadeira não está disponível, então ela é anulada (vira 'desconhecida' no DW) em vez de inventada. As medições são mantidas.")
def usi_v02(ctx):
    u = ctx["usina"]
    primeira = _medicao_valida_no_periodo(ctx).groupby("id_usina")["data_hora"].min()
    data_inicio = pd.to_datetime(u["data_inicio_operacao"])
    mascara = (data_inicio > pd.Timestamp.today()) | (data_inicio > u["id_usina"].map(primeira))
    return _filtro(u, mascara)


@regra("USI-K01", CONSISTENCIA, T_USI, "Coordenadas fora dos limites da UF declarada",
       "CORRIGIR", "Quando a latitude com o sinal invertido cai dentro da UF e do município do cadastro, o erro é de sinal (digitação). Corrige-se o sinal; sem isso o clima seria buscado no hemisfério norte.")
def usi_k01(ctx):
    u = ctx["usina"]
    return _filtro(u, v.coordenada_fora_da_uf(u, referencias.dentro_da_uf))


@regra("USI-K02", CONSISTENCIA, T_USI, "UF incompatível com o município (referência IBGE) ou com o submercado da usina",
       "CORRIGIR", "O município e as coordenadas apontam para outra UF, que também é a coerente com o submercado. Corrige-se a UF pela tabela de referência de municípios.")
def usi_k02(ctx):
    u = ctx["usina"]
    ref = ctx["municipios"].set_index("municipio")["uf"]
    uf_ref = u["municipio"].map(ref)
    mascara = (uf_ref.notna() & (uf_ref != u["uf"])) | (u["uf"].map(referencias.UF_SUBMERCADO) != u["cod_submercado"])
    return _filtro(u, mascara)


@regra("USI-V03", VALIDADE, T_USI, "Potência instalada nula, zero ou negativa",
       "SINALIZAR", "Sem potência não há fator de capacidade. Nenhuma ocorrência esperada; regra de proteção.")
def usi_v03(ctx):
    u = ctx["usina"]
    return _filtro(u, u["potencia_mw"].isna() | (u["potencia_mw"] <= 0))


@regra("SUB-C01", COMPLETUDE, T_SUB, "Submercados do SIN ausentes no cadastro (esperados SE, S, NE, N)",
       "SINALIZAR", "Os quatro submercados são domínio fixo; a falta de um impediria valorar a geração.")
def sub_c01(ctx):
    s = ctx["submercado"]
    esperado = pd.DataFrame({"cod_submercado": ["SE", "S", "NE", "N"]})
    faltando = esperado[~esperado["cod_submercado"].isin(s["cod_submercado"].str.strip())]
    return len(esperado), faltando


@regra("FON-V01", VALIDADE, T_FON, "Fonte com classificação inválida (intermitente não renovável ou código fora do domínio)",
       "SINALIZAR", "Domínio do negócio: só sol e vento são intermitentes, e ambos são renováveis.")
def fon_v01(ctx):
    f = ctx["fonte"]
    mascara = (f["intermitente"] & ~f["renovavel"]) | ~f["cod_fonte"].isin(["UHE", "PCH", "UFV", "EOL", "BIO", "UTE"])
    return _filtro(f, mascara)


@regra("FER-C01", COMPLETUDE, T_FER, "Anos cobertos pelos fatos (geração e PLD) sem feriados cadastrados",
       "COMPLEMENTAR", "O PLD vai até 2026, mas a origem só tem feriados de 2025. Sem eles a dimensão de tempo marcaria feriados de 2026 como dias úteis. Os feriados nacionais faltantes são calculados pelo calendário oficial (datas fixas em lei e móveis a partir da Páscoa) e marcados com origem CALCULADO.")
def fer_c01(ctx):
    anos = sorted(set(ctx["pld"]["data_hora"].dt.year.dropna().astype(int)) | {2025})
    cobertos = set(pd.to_datetime(ctx["feriado"]["data"]).dt.year)
    lista = pd.DataFrame({"ano": anos})
    return len(lista), lista[~lista["ano"].isin(cobertos)]


@regra("FER-V01", VALIDADE, T_FER, "Tipo de feriado fora do domínio ('Feriado' ou 'Ponto facultativo')",
       "SINALIZAR", "Domínio usado pela dimensão de tempo para definir dia útil.")
def fer_v01(ctx):
    f = ctx["feriado"]
    return _filtro(f, ~f["tipo"].isin(["Feriado", "Ponto facultativo"]))


@regra("PAR-V01", VALIDADE, T_PAR, "Parada com fim anterior ao início",
       "QUARENTENA", "Lançamento manual inconsistente. Inverter as datas seria um palpite, e as medições do período mostram a usina gerando normalmente, então a parada não é usada no cálculo de perdas e fica guardada para conferência com a operação.")
def par_v01(ctx):
    p = ctx["parada"]
    return _filtro(p, v.datas_invertidas(p, "inicio", "fim"))


@regra("PAR-I01", INTEGRIDADE, T_PAR, "Parada de usina inexistente no cadastro",
       "QUARENTENA", "Sem usina não há como calcular perda. Nenhuma ocorrência esperada (a origem tem chave estrangeira).")
def par_i01(ctx):
    p = ctx["parada"]
    return _filtro(p, v.sem_correspondencia(p, "id_usina", ctx["usina"]["id_usina"]))


@regra("PAR-K01", CONSISTENCIA, T_PAR, "Paradas sobrepostas para a mesma usina",
       "SINALIZAR", "Sobreposição contaria a mesma hora parada duas vezes. A fato de paradas usa grão horário com chave usina+hora, o que já impede dupla contagem.")
def par_k01(ctx):
    p = ctx["parada"]
    validas = p[~v.datas_invertidas(p, "inicio", "fim")]
    return len(p), validas[v.intervalos_sobrepostos(validas, "id_usina", "inicio", "fim")]


@regra("MED-C01", COMPLETUDE, T_MED, "Energia gerada nula",
       "CORRIGIR", "Falha de comunicação de poucas horas. A energia é estimada por interpolação linear entre a hora anterior e a seguinte (só lacunas de até 6 h), marcada como ESTIMADO, e o valor original (nulo) fica preservado.")
def med_c01(ctx):
    m = ctx["medicao"]
    return _filtro(m, m["energia_mwh"].isna() & m["id_usina"].notna())


@regra("MED-C02", COMPLETUDE, T_MED, "Horas sem nenhuma medição para a usina no ano (esperado: 8.760 por usina)",
       "SINALIZAR", "Não se inventa um dia inteiro de vento ou de sol. As horas faltantes ficam fora do fato e o painel mostra a cobertura; inventar levaria a uma receita que não aconteceu.")
def med_c02(ctx):
    inicio, fim = _periodo()
    m = _medicao_valida_no_periodo(ctx)
    m = m[m["id_usina"].isin(ctx["usinas_canonicas"])]
    return v.lacunas_horarias(m, "id_usina", "data_hora", inicio, fim, ctx["usinas_canonicas"])


@regra("MED-C03", COMPLETUDE, T_MED, "Disponibilidade (MW) nula",
       "SINALIZAR", "A disponibilidade é informativa; a linha afetada é a mesma sem usina (MED-I01).")
def med_c03(ctx):
    m = ctx["medicao"]
    return _filtro(m, m["disponibilidade_mw"].isna())


@regra("MED-U01", UNICIDADE, T_MED, "Mesma usina e hora repetidas com a mesma origem (reprocessamento da integração)",
       "DESCARTAR", "As cópias têm a mesma energia e chegaram um dia depois. Mantém-se a primeira leitura recebida; as cópias inflariam a geração e a receita.")
def med_u01(ctx):
    m = ctx["medicao"]
    dup = v.duplicados(m, ["id_usina", "data_hora", "origem"])
    primeira = m.sort_values("recebido_em").duplicated(["id_usina", "data_hora", "origem"], keep="first").reindex(m.index)
    return _filtro(m, dup & primeira)


@regra("MED-U02", UNICIDADE, T_MED, "Lançamento MANUAL por cima de uma leitura SCADA da mesma usina e hora",
       "QUARENTENA", "A leitura automática (SCADA) é a medição oficial. O valor manual é 10% maior e não tem justificativa registrada, então vai para quarentena para auditoria em vez de substituir a leitura do medidor.")
def med_u02(ctx):
    m = ctx["medicao"]
    scada = m[m["origem"] == "SCADA"][["id_usina", "data_hora"]].drop_duplicates()
    manual = m[m["origem"] != "SCADA"].reset_index().merge(scada, on=["id_usina", "data_hora"]).set_index("index")
    return len(m), m.loc[manual.index]


@regra("MED-V01", VALIDADE, T_MED, "Energia gerada negativa",
       "CORRIGIR", "Valor negativo é consumo dos serviços auxiliares, não geração. Para o indicador de geração e receita ele vira 0; o valor original fica guardado em energia_original_mwh.")
def med_v01(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.fora_da_faixa(m, "energia_mwh", minimo=0))


@regra("MED-V02", VALIDADE, T_MED, "Data da medição fora do período de 2025",
       "QUARENTENA", "Ano 2052 é erro de digitação. A hora provável (mesmo dia e hora em 2025) já tem leitura SCADA, então corrigir o ano criaria uma duplicata; o registro vai para quarentena.")
def med_v02(ctx):
    m = ctx["medicao"]
    inicio, fim = _periodo()
    return _filtro(m, v.fora_do_periodo(m, "data_hora", inicio, fim) | m["data_hora"].isna())


@regra("MED-V03", VALIDADE, T_MED, "Dado recebido antes da hora medida (recebido_em < data_hora)",
       "SINALIZAR", "Impossível no mundo real: o erro está no relógio do servidor de integração, não na energia. A medição é mantida e sinalizada.")
def med_v03(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.evento_antes_de(m, "data_hora", "recebido_em"))


@regra("MED-I01", INTEGRIDADE, T_MED, "Medição sem usina ou com usina inexistente no cadastro",
       "SINALIZAR", "Não se sabe a qual usina a energia pertence. A linha vai para o DW ligada ao membro 'Desconhecido' (chave -1): o volume fica visível, mas não entra na receita porque não há submercado para buscar o PLD.")
def med_i01(ctx):
    m = ctx["medicao"]
    return _filtro(m, m["id_usina"].isna() | v.sem_correspondencia(m, "id_usina", ctx["usina"]["id_usina"]))


@regra("MED-A01", ACURACIA, T_MED, "Energia mais de 100 vezes maior que a potência instalada (unidade errada, kWh)",
       "CORRIGIR", "Lançamento MANUAL vindo de planilha em kWh: dividido por 1.000, o valor volta à faixa normal da usina e fica coerente com as horas vizinhas.")
def med_a01(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.acima_do_limite(m, "energia_mwh", "potencia_mw", 100))


@regra("MED-A02", ACURACIA, T_MED, "Energia acima da potência instalada em 1 hora (fisicamente impossível)",
       "CORRIGIR", "Se o valor dividido por 10 bate com as horas vizinhas, é vírgula deslocada e se divide por 10. Se não bate, é pico de leitura e o valor é estimado por interpolação (ESTIMADO).")
def med_a02(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.acima_do_limite(m, "energia_mwh", "potencia_mw", 1) & ~v.acima_do_limite(m, "energia_mwh", "potencia_mw", 100))


@regra("MED-A03", ACURACIA, T_MED, "Valor idêntico por 12 horas ou mais (medidor travado)",
       "SINALIZAR", "O valor travado é plausível (próximo do fator de capacidade típico da usina na safra), e não há leitura alternativa para substituir. A medição é mantida e sinalizada para a manutenção do medidor.")
def med_a03(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.sequencia_constante(m, "id_usina", "data_hora", "energia_mwh", config.qualidade()["horas_sensor_travado"]))


@regra("MED-K01", CONSISTENCIA, T_MED, "Geração solar entre 19h e 5h (sem sol)",
       "CORRIGIR", "Física: usina fotovoltaica não gera à noite. O valor é zerado e marcado como CORRIGIDO.")
def med_k01(ctx):
    m = ctx["medicao"]
    hora = m["data_hora"].dt.hour
    return _filtro(m, (m["cod_fonte"] == "UFV") & ((hora >= 19) | (hora <= 5)) & (m["energia_mwh"] > 0))


@regra("MED-K02", CONSISTENCIA, T_MED, "Geração maior que zero durante parada registrada da usina",
       "CORRIGIR", "Cruzamento entre tabelas: a usina estava em parada programada e a própria linha informa disponibilidade 0 MW. A energia é zerada.")
def med_k02(ctx):
    m = ctx["medicao"]
    paradas = ctx["parada"][~v.datas_invertidas(ctx["parada"], "inicio", "fim")]
    dentro = v.dentro_de_intervalos(m, "id_usina", "data_hora", paradas, "id_usina", "inicio", "fim")
    return _filtro(m, dentro & (m["energia_mwh"] > 0))


@regra("MED-K03", CONSISTENCIA, T_MED, "Energia maior que a disponibilidade informada na mesma hora",
       "SINALIZAR", "Indica erro em uma das duas colunas. Os casos são resolvidos pelas regras MED-A01, MED-A02 e MED-K02; esta regra mede o tamanho do problema.")
def med_k03(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.acima_do_limite(m, "energia_mwh", "disponibilidade_mw", 1.0) & m["disponibilidade_mw"].notna())


@regra("MED-K04", CONSISTENCIA, T_MED, "Medição sem PLD publicado para o submercado e a hora",
       "SINALIZAR", "Sem preço não há receita valorada. A geração entra no DW e a receita fica nula.")
def med_k04(ctx):
    m = _medicao_valida_no_periodo(ctx)
    m = m[m["cod_submercado"].notna()]
    precos = ctx["pld"][["cod_submercado", "data_hora"]].assign(tem=True)
    juncao = m.reset_index().merge(precos, on=["cod_submercado", "data_hora"], how="left").set_index("index")
    return len(m), m.loc[juncao[juncao["tem"].isna()].index]


@regra("MED-T01", ATUALIDADE, T_MED, "Medição recebida mais de 48 h depois da hora medida",
       "SINALIZAR", "O dado está correto, mas chegou tarde para o fechamento diário. É mantido e sinalizado para acompanhar o SLA da integração.")
def med_t01(ctx):
    m = ctx["medicao"]
    return _filtro(m, v.atraso_maior_que(m, "data_hora", "recebido_em", config.qualidade()["atraso_maximo_horas"]))


@regra("MED-T02", ATUALIDADE, T_MED, "Usina que parou de enviar dados antes do fim do período",
       "SINALIZAR", "A falta de dados no fim do ano não é geração zero. As horas ficam fora do fato e a usina é apontada para a operação.")
def med_t02(ctx):
    m = _medicao_valida_no_periodo(ctx)
    m = m[m["id_usina"].isin(ctx["usinas_canonicas"])]
    _, fim = _periodo()
    atrasadas = v.ultimo_registro_antes(m, "id_usina", "data_hora", pd.Timestamp(fim) - pd.Timedelta(hours=24))
    return len(ctx["usinas_canonicas"]), atrasadas


@regra("PLD-C01", COMPLETUDE, T_PLD, "Horas sem PLD por submercado nos meses publicados",
       "SINALIZAR", "Preço não se inventa: horas sem PLD deixam a receita daquela hora nula.")
def pld_c01(ctx):
    p = ctx["pld"]
    if p.empty:
        return 0, p
    return v.lacunas_horarias(p, "cod_submercado", "data_hora", p["data_hora"].min().normalize(),
                              p["data_hora"].max().normalize() + pd.Timedelta(hours=23), ["SE", "S", "NE", "N"])


@regra("PLD-U01", UNICIDADE, T_PLD_RAW, "Mesmo submercado e hora repetidos no raw da API",
       "DESCARTAR", "A API pode republicar registros. A camada tratada mantém só a extração mais recente de cada submercado e hora.")
def pld_u01(ctx):
    r = ctx["pld_raw"]
    if r.empty:
        return 0, r
    validos = r.dropna(subset=["cod_submercado", "data_hora"])
    return len(r), validos[validos.sort_values("extraido_em").duplicated(["cod_submercado", "data_hora"], keep="last").reindex(validos.index)]


@regra("PLD-V01", VALIDADE, T_PLD, "PLD fora dos limites regulatórios do ano (piso e teto horário da ANEEL)",
       "QUARENTENA", "A CCEE aplica piso e teto antes de publicar; valor fora deles é erro de carga. O registro sai do caminho e fica em quarentena.")
def pld_v01(ctx):
    p = ctx["pld"]
    limites = config.limites_pld()
    piso = p["data_hora"].dt.year.map(lambda a: limites.get(a, (None, None))[0])
    teto = p["data_hora"].dt.year.map(lambda a: limites.get(a, (None, None))[1])
    return _filtro(p, ((p["pld_rs_mwh"] < piso - 0.01) | (p["pld_rs_mwh"] > teto + 0.01)) & piso.notna())


@regra("PLD-V02", VALIDADE, T_PLD_RAW, "Registro do raw com submercado, data, hora ou valor que não pode ser convertido",
       "QUARENTENA", "Sem esses campos o registro não tem grão; vai para quarentena com o JSON original.")
def pld_v02(ctx):
    r = ctx["pld_raw"]
    if r.empty:
        return 0, r
    return _filtro(r, r[["cod_submercado", "data_hora", "pld_rs_mwh"]].isna().any(axis=1))


@regra("PLD-K01", CONSISTENCIA, T_PLD_RAW, "MES_REFERENCIA ou PERIODO_COMERCIALIZACAO incoerentes com DIA e HORA",
       "SINALIZAR", "Campos derivados devem bater com a data. O DW usa DIA+HORA como verdade, por isso apenas sinaliza.")
def pld_k01(ctx):
    r = ctx["pld_raw"]
    if r.empty:
        return 0, r
    ok = r.dropna(subset=["data_hora"])
    mes = ok["data_hora"].dt.strftime("%Y%m") != ok["mes_referencia"]
    periodo = ok["periodo_comercializacao"] != ((ok["data_hora"].dt.day - 1) * 24 + ok["data_hora"].dt.hour + 1)
    return len(r), ok[mes | periodo]


@regra("PLD-A01", ACURACIA, T_PLD, "PLD muito distante do padrão do mês no submercado (z robusto > 6)",
       "SINALIZAR", "O PLD horário tem picos legítimos (dentro do teto). O valor é mantido e sinalizado para análise, sem descarte.")
def pld_a01(ctx):
    p = ctx["pld"].assign(mes=ctx["pld"]["data_hora"].dt.to_period("M").astype(str))
    return _filtro(p, v.outlier_robusto(p, ["cod_submercado", "mes"], "pld_rs_mwh", 6.0))


@regra("PLD-T01", ATUALIDADE, T_PLD, "Último mês publicado com mais de 2 meses de atraso em relação a hoje",
       "SINALIZAR", "Mostra se a extração está trazendo o dado mais recente disponível.")
def pld_t01(ctx):
    p = ctx["pld"]
    if p.empty:
        return 1, pd.DataFrame({"ultimo_mes": [None]})
    ultimo = p["data_hora"].max().to_period("M")
    atraso = (pd.Timestamp.today().to_period("M") - ultimo).n
    resultado = pd.DataFrame({"ultimo_mes": [str(ultimo)], "meses_atraso": [atraso]})
    return 1, resultado[resultado["meses_atraso"] > 2]


@regra("CLI-C01", COMPLETUDE, T_CLI, "Horas sem clima por usina no período baixado",
       "SINALIZAR", "Clima é variável explicativa; hora faltante fica nula e não entra nas correlações.", "clima")
def cli_c01(ctx):
    c = ctx["clima"]
    cfg = config.openmeteo()
    return v.lacunas_horarias(c, "cod_usina", "data_hora", cfg["data_inicio"], f"{cfg['data_fim']} 23:00", ctx["usina"]["cod_usina"].tolist())


@regra("CLI-C02", COMPLETUDE, T_CLI, "Variáveis de clima nulas",
       "SINALIZAR", "A API do Open-Meteo devolve nulo quando não tem a variável naquele ponto; mantém-se nulo.", "clima")
def cli_c02(ctx):
    c = ctx["clima"]
    return _filtro(c, v.nulos(c, ["temperatura_c", "radiacao_w_m2", "vento_100m_ms"]))


@regra("CLI-U01", UNICIDADE, T_CLI, "Mesma usina e hora repetidas no clima",
       "DESCARTAR", "Grão 1 ponto x 1 hora; repetição viria de duas extrações sobrepostas.", "clima")
def cli_u01(ctx):
    c = ctx["clima"]
    return _filtro(c, v.duplicados(c, ["cod_usina", "data_hora"]))


@regra("CLI-V01", VALIDADE, T_CLI, "Clima fora da faixa física (radiação 0 a 1.400 W/m², vento 0 a 60 m/s, temperatura -10 a 50 °C)",
       "CORRIGIR", "Valor fisicamente impossível vira nulo (não usado), para não distorcer as correlações.", "clima")
def cli_v01(ctx):
    c = ctx["clima"]
    mascara = (v.fora_da_faixa(c, "radiacao_w_m2", 0, 1400) | v.fora_da_faixa(c, "vento_100m_ms", 0, 60)
               | v.fora_da_faixa(c, "temperatura_c", -10, 50))
    return _filtro(c, mascara)


@regra("CLI-K01", CONSISTENCIA, T_CLI, "Radiação solar acima de 50 W/m² entre 0h e 4h (fuso horário trocado)",
       "SINALIZAR", "Radiação de madrugada indica dado em UTC tratado como horário de Brasília. A extração pede timezone=America/Sao_Paulo; a regra confirma.", "clima")
def cli_k01(ctx):
    c = ctx["clima"]
    return _filtro(c, (c["data_hora"].dt.hour <= 4) & (c["radiacao_w_m2"] > 50))


@regra("CLI-I01", INTEGRIDADE, T_CLI, "Ponto de clima sem usina correspondente no cadastro tratado",
       "DESCARTAR", "O ponto de clima só tem sentido associado a uma usina.", "clima")
def cli_i01(ctx):
    c = ctx["clima"]
    return _filtro(c, v.sem_correspondencia(c, "cod_usina", ctx["usina"]["cod_usina"]))


@regra("CLI-A01", ACURACIA, T_CLI, "Vento idêntico por 24 horas ou mais (série congelada)",
       "SINALIZAR", "Série congelada indica preenchimento do provedor. É mantida e sinalizada.", "clima")
def cli_a01(ctx):
    c = ctx["clima"]
    return _filtro(c, v.sequencia_constante(c, "cod_usina", "data_hora", "vento_100m_ms", 24))


@regra("CLI-T01", ATUALIDADE, T_CLI, "Usina cujo clima termina antes do fim do período configurado",
       "SINALIZAR", "Mostra se a extração cobriu todo o período pedido.", "clima")
def cli_t01(ctx):
    c = ctx["clima"]
    cfg = config.openmeteo()
    return len(ctx["usina"]), v.ultimo_registro_antes(c, "cod_usina", "data_hora", f"{cfg['data_fim']} 23:00")


def por_escopo(escopo):
    return [r for r in REGRAS if r.escopo == escopo]
