"""Cores e fontes da interface."""

from __future__ import annotations

import customtkinter as ctk

FUNDO = "#0f1216"
LATERAL = "#151920"
CARTAO = "#1b2028"
BORDA = "#2a313b"
TEXTO = "#e6e9ed"
TEXTO_SECUNDARIO = "#98a2ae"
DESTAQUE = "#3b82f6"
DESTAQUE_HOVER = "#2563eb"
SECUNDARIO = "#2a313b"
SECUNDARIO_HOVER = "#363e4a"

NIVEIS = {
    "ok": "#22a559",
    "info": "#3b82f6",
    "aviso": "#d97706",
    "erro": "#dc2626",
    "neutro": "#4b5563",
}


def fonte(tamanho: int = 13, negrito: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=tamanho, weight="bold" if negrito else "normal")
