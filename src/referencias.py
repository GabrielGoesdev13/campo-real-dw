from datetime import date, timedelta

import pandas as pd

from src import config

UF_SUBMERCADO = {
    "SP": "SE", "RJ": "SE", "MG": "SE", "ES": "SE", "GO": "SE", "DF": "SE", "MT": "SE", "MS": "SE", "AC": "SE", "RO": "SE",
    "PR": "S", "SC": "S", "RS": "S",
    "BA": "NE", "SE": "NE", "AL": "NE", "PE": "NE", "PB": "NE", "RN": "NE", "CE": "NE", "PI": "NE",
    "PA": "N", "TO": "N", "MA": "N", "AP": "N", "AM": "N", "RR": "N",
}

UF_LIMITES = {
    "AC": (-11.2, -7.1, -74.0, -66.6), "AL": (-10.5, -8.8, -38.3, -35.1), "AP": (-1.3, 4.5, -54.9, -49.8),
    "AM": (-9.9, 2.3, -73.8, -56.1), "BA": (-18.4, -8.5, -46.7, -37.3), "CE": (-7.9, -2.7, -41.5, -37.2),
    "DF": (-16.1, -15.5, -48.3, -47.3), "ES": (-21.3, -17.9, -41.9, -39.6), "GO": (-19.5, -12.4, -53.3, -45.9),
    "MA": (-10.3, -1.0, -48.8, -41.8), "MT": (-18.1, -7.3, -61.7, -50.2), "MS": (-24.1, -17.2, -58.2, -50.9),
    "MG": (-22.95, -14.2, -51.1, -39.8), "PA": (-9.9, 2.6, -58.9, -46.0), "PB": (-8.3, -6.0, -38.8, -34.8),
    "PR": (-26.8, -22.5, -54.7, -48.0), "PE": (-9.5, -7.3, -41.4, -34.8), "PI": (-10.95, -2.7, -45.95, -40.4),
    "RJ": (-23.4, -20.7, -44.9, -40.9), "RN": (-6.99, -4.8, -38.6, -34.9), "RS": (-33.8, -27.0, -57.7, -49.7),
    "RO": (-13.7, -7.9, -66.8, -59.8), "RR": (-1.6, 5.3, -64.9, -58.9), "SC": (-29.4, -25.9, -53.9, -48.3),
    "SP": (-25.4, -19.7, -53.1, -44.1), "SE": (-11.6, -9.5, -38.3, -36.4), "TO": (-13.5, -5.1, -50.8, -45.7),
}


def dentro_da_uf(uf, latitude, longitude):
    limites = UF_LIMITES.get(uf)
    if limites is None or pd.isna(latitude) or pd.isna(longitude):
        return False
    lat_min, lat_max, lon_min, lon_max = limites
    return lat_min <= float(latitude) <= lat_max and lon_min <= float(longitude) <= lon_max


def municipios():
    return pd.read_csv(config.PASTA_CONFIG / "referencia_municipios.csv")


def pascoa(ano):
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano):
    p = pascoa(ano)
    lista = [
        (date(ano, 1, 1), "Confraternização Universal", "Feriado"),
        (p - timedelta(days=48), "Carnaval", "Ponto facultativo"),
        (p - timedelta(days=47), "Carnaval", "Ponto facultativo"),
        (p - timedelta(days=2), "Sexta-feira Santa", "Feriado"),
        (date(ano, 4, 21), "Tiradentes", "Feriado"),
        (date(ano, 5, 1), "Dia do Trabalho", "Feriado"),
        (p + timedelta(days=60), "Corpus Christi", "Ponto facultativo"),
        (date(ano, 9, 7), "Independência do Brasil", "Feriado"),
        (date(ano, 10, 12), "Nossa Senhora Aparecida", "Feriado"),
        (date(ano, 11, 2), "Finados", "Feriado"),
        (date(ano, 11, 15), "Proclamação da República", "Feriado"),
        (date(ano, 11, 20), "Dia da Consciência Negra", "Feriado"),
        (date(ano, 12, 25), "Natal", "Feriado"),
    ]
    return pd.DataFrame(lista, columns=["data", "descricao", "tipo"])
