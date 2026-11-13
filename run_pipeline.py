import argparse
import logging
import sys
import time

from src import db

ETAPAS = ["estrutura", "pld", "qualidade_origem", "clima", "qualidade_clima", "dw", "relatorio"]
OPCIONAIS = ["pld_simulado"]


def etapa_estrutura():
    db.executar_arquivo("01_estrutura_etl.sql")
    db.executar_arquivo("10_dw_ddl.sql")


def etapa_pld(forcar):
    from src.extracao import pld_ccee
    pld_ccee.executar(forcar=forcar)


def etapa_pld_simulado():
    from src.extracao import pld_simulado
    pld_simulado.executar()


def etapa_qualidade_origem():
    from src.qualidade import executor
    executor.executar("origem")


def etapa_clima(forcar):
    from src.extracao import clima_openmeteo
    clima_openmeteo.extrair(forcar=forcar)


def etapa_qualidade_clima():
    from src.qualidade import executor
    executor.executar("clima")


def etapa_dw():
    from src.dw import carga
    carga.executar()


def etapa_relatorio():
    from src.qualidade import relatorio
    relatorio.gerar()


def main():
    parser = argparse.ArgumentParser(description="Pipeline do Data Warehouse da Campo Real Energia")
    parser.add_argument("--etapas", default=",".join(ETAPAS), help=f"Etapas separadas por virgula. Opcoes: {', '.join(ETAPAS + OPCIONAIS)}")
    parser.add_argument("--forcar", action="store_true", help="Baixa de novo dados que ja estao no raw")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    funcoes = {
        "estrutura": etapa_estrutura,
        "pld": lambda: etapa_pld(args.forcar),
        "pld_simulado": etapa_pld_simulado,
        "qualidade_origem": etapa_qualidade_origem,
        "clima": lambda: etapa_clima(args.forcar),
        "qualidade_clima": etapa_qualidade_clima,
        "dw": etapa_dw,
        "relatorio": etapa_relatorio,
    }
    pedidas = [e.strip() for e in args.etapas.split(",") if e.strip()]
    for etapa in pedidas:
        if etapa not in funcoes:
            sys.exit(f"Etapa desconhecida: {etapa}")
    for etapa in pedidas:
        inicio = time.time()
        logging.info("===== Etapa: %s =====", etapa)
        funcoes[etapa]()
        logging.info("Etapa %s concluida em %.1fs", etapa, time.time() - inicio)


if __name__ == "__main__":
    main()
