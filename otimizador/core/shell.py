"""Execução de comandos do Windows (PowerShell e executáveis) sem abrir janelas."""

from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("otimizador.shell")

CREATE_NO_WINDOW = 0x08000000

# Garante saída em UTF-8, sem barras de progresso e com erros em texto simples
# (sem isso, erros do PowerShell 5.1 podem vir em formato CLIXML).
_PREFIXO_PS = (
    "$ProgressPreference='SilentlyContinue';"
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
    "$ErrorActionPreference='Stop';"
    "try {{\n{script}\n}} catch {{ [Console]::Error.WriteLine($_.Exception.Message); exit 1 }}"
)


class ErroComando(RuntimeError):
    """Um comando terminou com erro."""


@dataclass
class Saida:
    codigo: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.codigo == 0

    def erro(self) -> str:
        return (self.stderr or self.stdout).strip() or f"código de saída {self.codigo}"


def _decodificar(dados: bytes) -> str:
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        # Ferramentas nativas (fsutil, powercfg) usam a página de código OEM do console.
        return dados.decode("oem", errors="replace")


def _limpar_clixml(texto: str) -> str:
    if not texto.lstrip().startswith("#< CLIXML"):
        return texto
    partes = re.findall(r'<S S="Error">(.*?)</S>', texto, flags=re.S)
    return "".join(partes).replace("_x000D__x000A_", "\n").strip()


def executar(args: list[str], timeout: int = 60) -> Saida:
    """Executa um programa e devolve código, stdout e stderr."""
    log.debug("Executando: %s", subprocess.list2cmdline(args))
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return Saida(127, "", f"Programa não encontrado: {args[0]}")
    except subprocess.TimeoutExpired:
        return Saida(124, "", f"Tempo esgotado ({timeout}s) ao executar {args[0]}")
    saida = Saida(proc.returncode, _decodificar(proc.stdout), _limpar_clixml(_decodificar(proc.stderr)))
    if not saida.ok:
        log.debug("Falhou (%s): %s", saida.codigo, saida.erro()[:500])
    return saida


def powershell(script: str, timeout: int = 120) -> Saida:
    """Executa um script no Windows PowerShell 5.1 (sempre presente no Windows 10/11)."""
    completo = _PREFIXO_PS.format(script=script)
    codificado = base64.b64encode(completo.encode("utf-16-le")).decode("ascii")
    return executar(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", codificado],
        timeout=timeout,
    )


def powershell_json(script: str, timeout: int = 120) -> Any:
    """Executa um script cujo resultado é convertido em JSON e devolve o objeto Python."""
    saida = powershell(f"& {{\n{script}\n}} | ConvertTo-Json -Depth 5 -Compress", timeout=timeout)
    if not saida.ok:
        raise ErroComando(saida.erro())
    texto = saida.stdout.strip()
    return json.loads(texto) if texto else None


def como_lista(valor: Any) -> list:
    """ConvertTo-Json devolve um objeto quando há um item só; normaliza para lista."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]
