"""Ponto de restauração do sistema, criado antes da primeira alteração da sessão."""

from __future__ import annotations

import logging
import winreg
from dataclasses import dataclass
from datetime import datetime, timedelta

from .shell import ErroComando, como_lista, powershell, powershell_json

log = logging.getLogger("otimizador.restauracao")

DESCRICAO_PADRAO = "Otimizador de PC - antes dos ajustes"

# O Windows ignora pedidos de novo ponto se já existe um criado nas últimas 24h.
INTERVALO_MINIMO = timedelta(hours=24)


@dataclass
class PontoRestauracao:
    descricao: str
    data: datetime


@dataclass
class ResultadoRestauracao:
    status: str  # "criado" | "recente" | "desativado" | "erro"
    mensagem: str
    ponto: PontoRestauracao | None = None

    @property
    def protegido(self) -> bool:
        return self.status in ("criado", "recente")


def protecao_ativa() -> bool:
    """Lê se a Restauração do Sistema está habilitada (e não bloqueada por política)."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore") as chave:
            if winreg.QueryValueEx(chave, "DisableSR")[0] == 1:
                return False
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore") as chave:
            return winreg.QueryValueEx(chave, "RPSessionInterval")[0] == 1
    except OSError:
        return False


def listar_pontos() -> list[PontoRestauracao]:
    dados = powershell_json(
        "@(Get-ComputerRestorePoint | ForEach-Object { [pscustomobject]@{"
        " Descricao = $_.Description;"
        " Data = $_.ConvertToDateTime($_.CreationTime).ToString('s') } })"
    )
    pontos = [PontoRestauracao(p["Descricao"], datetime.fromisoformat(p["Data"]))
              for p in como_lista(dados)]
    return sorted(pontos, key=lambda p: p.data)


def ativar_protecao() -> None:
    log.info("Ativando a Proteção do Sistema na unidade do Windows...")
    saida = powershell('Enable-ComputerRestore -Drive "$env:SystemDrive\\"', timeout=120)
    if not saida.ok:
        raise ErroComando(f"Não foi possível ativar a Proteção do Sistema: {saida.erro()}")
    log.info("Proteção do Sistema ativada.")


def criar_ponto(descricao: str = DESCRICAO_PADRAO) -> ResultadoRestauracao:
    if not protecao_ativa():
        return ResultadoRestauracao("desativado", "A Proteção do Sistema está desativada.")

    try:
        antes = listar_pontos()
    except ErroComando as erro:
        return ResultadoRestauracao("erro", f"Não foi possível listar os pontos de restauração: {erro}")

    if antes and datetime.now() - antes[-1].data < INTERVALO_MINIMO:
        ultimo = antes[-1]
        msg = (f"Já existe um ponto de restauração recente ({ultimo.data:%d/%m/%Y %H:%M}, "
               f"\"{ultimo.descricao}\"). O Windows permite só um a cada 24h, então ele será usado.")
        log.info(msg)
        return ResultadoRestauracao("recente", msg, ultimo)

    log.info("Criando ponto de restauração (pode levar até alguns minutos)...")
    saida = powershell(
        f"Checkpoint-Computer -Description '{descricao.replace(chr(39), '')}' "
        "-RestorePointType MODIFY_SETTINGS",
        timeout=600,
    )
    if not saida.ok:
        return ResultadoRestauracao("erro", f"Falha ao criar o ponto de restauração: {saida.erro()}")

    depois = listar_pontos()
    novos = [p for p in depois if p not in antes]
    if not novos:
        return ResultadoRestauracao("erro", "O Windows não criou o ponto de restauração.")
    msg = f"Ponto de restauração criado: \"{novos[-1].descricao}\" ({novos[-1].data:%d/%m/%Y %H:%M})."
    log.info(msg)
    return ResultadoRestauracao("criado", msg, novos[-1])
