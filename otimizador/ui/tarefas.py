"""Executa funções lentas em segundo plano sem travar a janela.

O Tkinter não é thread-safe: a thread só coloca o resultado em uma fila,
e a thread da interface consome essa fila periodicamente.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable

log = logging.getLogger("otimizador.ui")


class Executor:
    INTERVALO_MS = 80

    def __init__(self, raiz: Any) -> None:
        self.raiz = raiz
        self._fila: queue.Queue[tuple[Callable[..., None], tuple[Any, ...]]] = queue.Queue()
        self.raiz.after(self.INTERVALO_MS, self._processar)

    def rodar(self, funcao: Callable[[], Any], ao_terminar: Callable[[Any], None],
              ao_falhar: Callable[[Exception], None] | None = None) -> None:
        def alvo() -> None:
            try:
                resultado = funcao()
            except Exception as erro:  # noqa: BLE001
                log.exception("Erro em tarefa de segundo plano")
                if ao_falhar:
                    self._fila.put((ao_falhar, (erro,)))
                return
            self._fila.put((ao_terminar, (resultado,)))

        threading.Thread(target=alvo, daemon=True).start()

    def _processar(self) -> None:
        try:
            while True:
                callback, args = self._fila.get_nowait()
                try:
                    callback(*args)
                except Exception:  # noqa: BLE001
                    log.exception("Erro ao atualizar a interface")
        except queue.Empty:
            pass
        self.raiz.after(self.INTERVALO_MS, self._processar)
