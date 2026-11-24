"""Ponto de entrada: pede administrador, configura o log e abre a janela."""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import tkinter as tk
from tkinter import messagebox

from . import APP_NOME
from .core import admin
from .core.log import configurar_log


def _perguntar_modo_leitura() -> bool:
    raiz = tk.Tk()
    raiz.withdraw()
    resposta = messagebox.askyesno(
        APP_NOME,
        "Sem permissão de administrador o app não consegue aplicar ajustes nem criar o ponto de "
        "restauração.\n\nAbrir apenas o diagnóstico (modo somente leitura)?",
    )
    raiz.destroy()
    return resposta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="otimizador", description=APP_NOME)
    parser.add_argument("--sem-admin", action="store_true",
                        help="não pede elevação; abre em modo somente leitura")
    args = parser.parse_args(argv)

    eh_admin = admin.eh_admin()
    if not eh_admin and not args.sem_admin:
        if admin.reabrir_como_admin():
            return 0  # a cópia elevada assume daqui
        if not _perguntar_modo_leitura():
            return 1

    fila: queue.Queue[str] = queue.Queue()
    arquivo_log = configurar_log(fila)
    logging.getLogger("otimizador").info(
        "Modo: %s", "administrador" if eh_admin else "somente leitura (sem administrador)")

    from .ui.app import App  # importa a interface só depois da elevação

    App(eh_admin, arquivo_log, fila).mainloop()
    logging.getLogger("otimizador").info("App encerrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
