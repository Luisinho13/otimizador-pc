"""Log em arquivo (um por sessão) e encaminhamento das mensagens para a interface."""

from __future__ import annotations

import logging
import os
import platform
import queue
from datetime import datetime
from pathlib import Path

from .. import APP_NOME, __version__

FORMATO = "%(asctime)s [%(levelname)s] %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def pasta_dados() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    pasta = Path(base) / "OtimizadorPC"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def pasta_logs() -> Path:
    pasta = pasta_dados() / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


class FilaHandler(logging.Handler):
    """Coloca cada linha de log em uma fila lida pela interface (thread-safe)."""

    def __init__(self, fila: queue.Queue[str]) -> None:
        super().__init__(level=logging.INFO)
        self.fila = fila

    def emit(self, registro: logging.LogRecord) -> None:
        try:
            self.fila.put_nowait(self.format(registro))
        except Exception:  # noqa: BLE001 - log nunca deve derrubar o app
            self.handleError(registro)


def configurar_log(fila: queue.Queue[str] | None = None) -> Path:
    """Configura o logger 'otimizador' e devolve o caminho do arquivo desta sessão."""
    arquivo = pasta_logs() / f"{datetime.now():%Y-%m-%d_%H%M%S}.log"
    formatador = logging.Formatter(FORMATO, FORMATO_DATA)

    raiz = logging.getLogger("otimizador")
    raiz.setLevel(logging.DEBUG)
    raiz.handlers.clear()

    arquivo_handler = logging.FileHandler(arquivo, encoding="utf-8")
    arquivo_handler.setLevel(logging.DEBUG)  # no arquivo vai tudo, inclusive comandos
    arquivo_handler.setFormatter(formatador)
    raiz.addHandler(arquivo_handler)

    if fila is not None:
        fila_handler = FilaHandler(fila)
        fila_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        raiz.addHandler(fila_handler)

    raiz.info("%s %s iniciado", APP_NOME, __version__)
    raiz.debug("Windows %s | Python %s", platform.version(), platform.python_version())
    return arquivo
