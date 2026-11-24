"""Verificação e solicitação de privilégios de administrador (UAC)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys


def eh_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _comando_atual() -> tuple[str, list[str]]:
    """Descobre como o app foi iniciado para reabri-lo do mesmo jeito."""
    if getattr(sys, "frozen", False):  # executável gerado pelo PyInstaller
        return sys.executable, sys.argv[1:]

    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw  # evita abrir uma janela de console extra

    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    if spec is not None and spec.name:  # iniciado com "python -m otimizador"
        modulo = spec.name.removesuffix(".__main__")
        return exe, ["-m", modulo, *sys.argv[1:]]
    return exe, [os.path.abspath(sys.argv[0]), *sys.argv[1:]]


def reabrir_como_admin() -> bool:
    """Abre o prompt do UAC. Retorna False se o usuário recusar ou houver erro."""
    exe, args = _comando_atual()
    resultado = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", exe, subprocess.list2cmdline(args), os.getcwd(), 1
    )
    return resultado > 32  # valores <= 32 indicam erro (ex.: UAC cancelado)
