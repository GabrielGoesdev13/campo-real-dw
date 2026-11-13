import logging
import traceback
from contextlib import contextmanager

from src import db

log = logging.getLogger(__name__)


class Execucao:
    def __init__(self, id_execucao):
        self.id = id_execucao
        self.linhas_lidas = 0
        self.linhas_gravadas = 0
        self.status = None
        self.mensagens = []

    def aviso(self, mensagem):
        log.warning(mensagem)
        self.mensagens.append(mensagem)


@contextmanager
def registrar(processo, fonte, parametros=None, propagar_erro=False):
    id_execucao = db.escalar(
        """INSERT INTO controle.log_execucao (processo, fonte, parametros, status)
           VALUES (:p, :f, CAST(:par AS jsonb), 'EXECUTANDO') RETURNING id_execucao""",
        {"p": processo, "f": fonte, "par": db.para_json(parametros or {})},
    )
    execucao = Execucao(id_execucao)
    erro_texto = None
    try:
        yield execucao
        status = execucao.status or "SUCESSO"
    except Exception as erro:
        status = "FALHA"
        erro_texto = f"{type(erro).__name__}: {erro}"
        log.error("%s falhou: %s", processo, erro_texto)
        log.debug(traceback.format_exc())
        if propagar_erro:
            _finalizar(execucao, status, erro_texto)
            raise
    _finalizar(execucao, status, erro_texto)


def _finalizar(execucao, status, erro_texto):
    mensagem = " | ".join(m for m in [erro_texto, *execucao.mensagens] if m) or None
    db.executar(
        """UPDATE controle.log_execucao
              SET fim = now(), linhas_lidas = :l, linhas_gravadas = :g, status = :s, mensagem_erro = :m
            WHERE id_execucao = :id""",
        {"l": execucao.linhas_lidas, "g": execucao.linhas_gravadas, "s": status, "m": mensagem, "id": execucao.id},
    )
    log.info("[log %s] status=%s lidas=%s gravadas=%s", execucao.id, status, execucao.linhas_lidas, execucao.linhas_gravadas)
