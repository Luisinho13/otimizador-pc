"""TRIM ativado + ReTrim manual nos SSDs (nunca em HDs)."""

from __future__ import annotations

import logging

from ..core.shell import como_lista, executar, powershell, powershell_json
from ..diagnostico.coleta import coletar_trim
from ..diagnostico.sistema import analisar_trim
from .base import Ajuste, Resultado, StatusAjuste

log = logging.getLogger("otimizador.ajustes")

SCRIPT_VOLUMES_SSD = r"""
$ssd = @(Get-PhysicalDisk | Where-Object { [string]$_.MediaType -eq 'SSD' -or [string]$_.BusType -eq 'NVMe' } |
         ForEach-Object { [string]$_.DeviceId })
@(Get-Partition | Where-Object { $_.DriveLetter -and ($ssd -contains [string]$_.DiskNumber) } |
  ForEach-Object { [string]$_.DriveLetter } | Sort-Object -Unique)
"""


def letras_ssd() -> list[str]:
    return [str(letra) for letra in como_lista(powershell_json(SCRIPT_VOLUMES_SSD))]


class TrimSsd(Ajuste):
    id = "trim"
    titulo = "TRIM + ReTrim nos SSDs"
    explicacao = (
        "O TRIM avisa o SSD quais blocos foram apagados, mantendo a velocidade de escrita ao longo do "
        "tempo. O Windows já costuma deixá-lo ligado; este ajuste confirma isso e executa um ReTrim "
        "agora nos volumes que estão em SSD. Discos mecânicos (HD) são ignorados."
    )
    tecnico = "fsutil behavior set DisableDeleteNotify 0  +  Optimize-Volume -DriveLetter X -ReTrim"
    texto_botao = "Ativar e executar ReTrim"
    repetivel = True

    def status(self) -> StatusAjuste:
        letras = letras_ssd()
        if not letras:
            return StatusAjuste("Nenhum SSD com letra de unidade encontrado", "neutro", disponivel=False)
        unidades = ", ".join(f"{letra}:" for letra in letras)
        trim = analisar_trim(coletar_trim())
        if trim is False:
            return StatusAjuste(f"TRIM desativado · SSD: {unidades}", "aviso")
        return StatusAjuste(f"TRIM ativado · SSD: {unidades}", "ok", aplicado=True)

    def _aplicar(self, opcoes: set[str] | None) -> Resultado:
        letras = letras_ssd()
        if not letras:
            return Resultado(False, "Nenhum SSD encontrado.")

        if analisar_trim(coletar_trim()) is False:
            self.estado.guardar_original(self.id, 1)
            saida = executar(["fsutil", "behavior", "set", "DisableDeleteNotify", "0"])
            if not saida.ok:
                return Resultado(False, f"Falha ao ativar o TRIM: {saida.erro()}")
            log.info("TRIM ativado (DisableDeleteNotify = 0).")

        concluidas, falhas = [], []
        for letra in letras:
            log.info("Executando ReTrim em %s: (pode levar alguns minutos)...", letra)
            saida = powershell(f"Optimize-Volume -DriveLetter {letra} -ReTrim -Verbose 4>&1 | Out-String",
                               timeout=900)
            if saida.ok:
                concluidas.append(f"{letra}:")
                log.debug(saida.stdout.strip())
            else:
                falhas.append(f"{letra}: ({saida.erro()})")

        if falhas:
            return Resultado(False, f"ReTrim falhou em {', '.join(falhas)}"
                             + (f"; concluído em {', '.join(concluidas)}" if concluidas else ""))
        return Resultado(True, f"TRIM ativado e ReTrim concluído em {', '.join(concluidas)}.")

    def _desfazer(self, original: object) -> Resultado:
        saida = executar(["fsutil", "behavior", "set", "DisableDeleteNotify", str(original)])
        if not saida.ok:
            return Resultado(False, f"Falha ao restaurar: {saida.erro()}")
        return Resultado(True, "Configuração de TRIM anterior restaurada.")
