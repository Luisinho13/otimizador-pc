"""Componentes visuais reutilizáveis."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from . import tema


class Selo(ctk.CTkLabel):
    """Etiqueta colorida de status (OK, aviso...)."""

    def __init__(self, master: Any, texto: str, nivel: str = "neutro") -> None:
        super().__init__(master, text=f" {texto} ", font=tema.fonte(11, True), text_color="white",
                         fg_color=tema.NIVEIS.get(nivel, tema.NIVEIS["neutro"]), corner_radius=6, height=22)

    def atualizar(self, texto: str, nivel: str) -> None:
        self.configure(text=f" {texto} ", fg_color=tema.NIVEIS.get(nivel, tema.NIVEIS["neutro"]))


class TextoQuebrado(ctk.CTkLabel):
    """Rótulo cujo texto quebra conforme a largura do contêiner."""

    def __init__(self, master: Any, texto: str, tamanho: int = 13, cor: str = tema.TEXTO,
                 negrito: bool = False, margem: int = 0) -> None:
        super().__init__(master, text=texto, font=tema.fonte(tamanho, negrito), text_color=cor,
                         justify="left", anchor="w", wraplength=600)
        self._margem = margem
        master.bind("<Configure>", self._ajustar, add="+")

    def _ajustar(self, evento: Any) -> None:
        largura = max(200, int(evento.width / self._get_widget_scaling()) - self._margem)
        if abs(largura - self.cget("wraplength")) > 4:
            self.configure(wraplength=largura)


class Cartao(ctk.CTkFrame):
    """Moldura com título; o conteúdo vai em `self.corpo`."""

    def __init__(self, master: Any, titulo: str, subtitulo: str | None = None) -> None:
        super().__init__(master, fg_color=tema.CARTAO, corner_radius=12, border_width=1,
                         border_color=tema.BORDA)
        self.grid_columnconfigure(0, weight=1)
        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 4))
        cabecalho.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cabecalho, text=titulo, font=tema.fonte(15, True), text_color=tema.TEXTO,
                     anchor="w").grid(row=0, column=0, sticky="w")
        self.cabecalho = cabecalho
        if subtitulo:
            ctk.CTkLabel(cabecalho, text=subtitulo, font=tema.fonte(12), text_color=tema.TEXTO_SECUNDARIO,
                         anchor="e").grid(row=0, column=1, sticky="e")
        self.corpo = ctk.CTkFrame(self, fg_color="transparent")
        self.corpo.grid(row=1, column=0, sticky="nsew", padx=18, pady=(4, 16))
        self.corpo.grid_columnconfigure(1, weight=1)
        self._linha = 0

    def linha(self, rotulo: str, valor: str, nivel: str | None = None) -> None:
        """Adiciona uma linha 'rótulo: valor' (com selo opcional)."""
        ctk.CTkLabel(self.corpo, text=rotulo, font=tema.fonte(13), text_color=tema.TEXTO_SECUNDARIO,
                     anchor="nw").grid(row=self._linha, column=0, sticky="nw", padx=(0, 16), pady=3)
        if nivel:
            Selo(self.corpo, valor, nivel).grid(row=self._linha, column=1, sticky="w", pady=3)
        else:
            TextoQuebrado(self.corpo, valor, margem=150).grid(row=self._linha, column=1, sticky="w", pady=3)
        self._linha += 1

    def proxima_linha(self) -> int:
        self._linha += 1
        return self._linha - 1


def botao(master: Any, texto: str, comando: Any, primario: bool = True, largura: int = 140) -> ctk.CTkButton:
    return ctk.CTkButton(
        master, text=texto, command=comando, width=largura, height=34, corner_radius=8,
        font=tema.fonte(13, True),
        fg_color=tema.DESTAQUE if primario else tema.SECUNDARIO,
        hover_color=tema.DESTAQUE_HOVER if primario else tema.SECUNDARIO_HOVER,
        text_color_disabled="#7d8590",
    )


def cabecalho_tela(master: Any, titulo: str, subtitulo: str) -> ctk.CTkFrame:
    quadro = ctk.CTkFrame(master, fg_color="transparent")
    quadro.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(quadro, text=titulo, font=tema.fonte(24, True), text_color=tema.TEXTO,
                 anchor="w").grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(quadro, text=subtitulo, font=tema.fonte(13), text_color=tema.TEXTO_SECUNDARIO,
                 anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 0))
    return quadro
