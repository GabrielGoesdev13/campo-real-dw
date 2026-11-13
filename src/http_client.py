import logging
import time

import requests

log = logging.getLogger(__name__)


class ErroExtracao(Exception):
    pass


class ErroEsquema(ErroExtracao):
    pass



class ClienteHttp:
    def __init__(self, timeout=60, tentativas=5, espera_inicial=2, pausa=0.5):
        self.timeout = timeout
        self.tentativas = tentativas
        self.espera_inicial = espera_inicial
        self.pausa = pausa
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = "campo-real-dw/1.0 (trabalho academico)"
        self.total_tentativas_extras = 0
        self._ultima = 0.0

    def _respeitar_pausa(self):
        decorrido = time.monotonic() - self._ultima
        if decorrido < self.pausa:
            time.sleep(self.pausa - decorrido)
        self._ultima = time.monotonic()

    def get_json(self, url, params=None):
        espera = self.espera_inicial
        ultimo_erro = None
        for tentativa in range(1, self.tentativas + 1):
            self._respeitar_pausa()
            try:
                resposta = self.sessao.get(url, params=params, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as erro:
                ultimo_erro = f"{type(erro).__name__}: {erro}"
                log.warning("Tentativa %s/%s falhou (%s). Nova tentativa em %.0fs", tentativa, self.tentativas, ultimo_erro, espera)
                self._aguardar(espera, tentativa)
                espera *= 2
                continue

            if resposta.status_code == 429:
                retry_after = resposta.headers.get("Retry-After")
                pausa = float(retry_after) if retry_after and retry_after.replace(".", "").isdigit() else espera
                ultimo_erro = "HTTP 429 (limite de requisicoes)"
                log.warning("Limite de requisicoes atingido. Aguardando %.0fs", pausa)
                self._aguardar(pausa, tentativa)
                espera *= 2
                continue

            if resposta.status_code >= 500:
                ultimo_erro = f"HTTP {resposta.status_code}"
                log.warning("Servidor respondeu %s. Nova tentativa em %.0fs", resposta.status_code, espera)
                self._aguardar(espera, tentativa)
                espera *= 2
                continue

            if resposta.status_code != 200:
                raise ErroExtracao(f"HTTP {resposta.status_code} em {resposta.url}: {resposta.text[:300]}")

            if not resposta.content or not resposta.content.strip():
                ultimo_erro = "corpo da resposta vazio"
                self._aguardar(espera, tentativa)
                espera *= 2
                continue

            try:
                return resposta.json()
            except ValueError:
                ultimo_erro = "resposta nao e um JSON valido"
                self._aguardar(espera, tentativa)
                espera *= 2
                continue

        raise ErroExtracao(f"Falha apos {self.tentativas} tentativas em {url}: {ultimo_erro}")

    def _aguardar(self, segundos, tentativa):
        if tentativa < self.tentativas:
            self.total_tentativas_extras += 1
            time.sleep(segundos)
