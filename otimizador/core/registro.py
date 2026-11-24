"""Leitura e escrita de valores DWORD no registro do Windows."""

from __future__ import annotations

import logging
import winreg

log = logging.getLogger("otimizador.registro")

RAIZES = {winreg.HKEY_CURRENT_USER: "HKCU", winreg.HKEY_LOCAL_MACHINE: "HKLM"}


def ler_dword(raiz: int, caminho: str, nome: str) -> int | None:
    """Devolve o valor ou None se a chave/valor não existir."""
    try:
        with winreg.OpenKey(raiz, caminho) as chave:
            valor, _tipo = winreg.QueryValueEx(chave, nome)
            return int(valor)
    except (OSError, ValueError, TypeError):
        return None


def gravar_dword(raiz: int, caminho: str, nome: str, valor: int | None) -> None:
    """Grava o valor. None remove o valor (volta ao padrão do Windows)."""
    destino = f"{RAIZES.get(raiz, raiz)}\\{caminho}\\{nome}"
    if valor is None:
        try:
            with winreg.OpenKey(raiz, caminho, 0, winreg.KEY_SET_VALUE) as chave:
                winreg.DeleteValue(chave, nome)
            log.info("Registro: removido %s (volta ao padrão do Windows)", destino)
        except FileNotFoundError:
            pass
        return
    with winreg.CreateKeyEx(raiz, caminho, 0, winreg.KEY_SET_VALUE) as chave:
        winreg.SetValueEx(chave, nome, 0, winreg.REG_DWORD, int(valor))
    log.info("Registro: %s = %s", destino, valor)
