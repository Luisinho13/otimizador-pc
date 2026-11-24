"""Tela de log: mostra em tempo real tudo o que foi feito nesta sessão."""

from __future__ import annotations

import os
import queue
from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..core.log import pasta_logs
from . import tema
from .componentes import botao, cabecalho_tela


class TelaLog(ctk.CTkFrame):
    def __init__(self, master: Any, fila: queue.Queue[str], arquivo: Path) -> None:
        super().__init__(master, fg_color="transparent")
        self.fila = fila
        self.arquivo = arquivo
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        exibido = str(arquivo).replace(os.environ.get("LOCALAPPDATA", "\0"), "%LOCALAPPDATA%")
        topo = cabecalho_tela(self, "Log", f"Tudo o que foi verificado e alterado. Arquivo: {exibido}")
        topo.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        botoes = ctk.CTkFrame(topo, fg_color="transparent")
        botoes.grid(row=0, column=1, rowspan=2, sticky="e")
        botao(botoes, "Abrir arquivo", lambda: os.startfile(self.arquivo), primario=False, largura=120).pack(
            side="left", padx=(0, 8))
        botao(botoes, "Pasta de logs", lambda: os.startfile(pasta_logs()), primario=False, largura=120).pack(
            side="left")

        self.texto = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), fg_color=tema.CARTAO,
                                    border_color=tema.BORDA, border_width=1, corner_radius=12,
                                    text_color=tema.TEXTO, wrap="word")
        self.texto.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 24))
        self.texto.configure(state="disabled")
        self.after(200, self._ler_fila)

    def _ler_fila(self) -> None:
        linhas = []
        try:
            while True:
                linhas.append(self.fila.get_nowait())
        except queue.Empty:
            pass
        if linhas:
            self.texto.configure(state="normal")
            self.texto.insert("end", "\n".join(linhas) + "\n")
            self.texto.see("end")
            self.texto.configure(state="disabled")
        self.after(250, self._ler_fila)
