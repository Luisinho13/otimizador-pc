"""Agendamento de GPU acelerado por hardware (HAGS)."""

from __future__ import annotations

import winreg

from ..core import registro
from ..diagnostico.coleta import CHAVE_GRAPHICS, coletar_hags
from ..diagnostico.sistema import analisar_hags
from .base import Ajuste, Resultado, StatusAjuste

VALOR = "HwSchMode"
LIGADO = 2


class AgendamentoGpu(Ajuste):
    id = "agendamento_gpu"
    titulo = "Agendamento de GPU acelerado por hardware"
    explicacao = (
        "A própria placa de vídeo passa a organizar sua fila de trabalho, em vez do Windows. É "
        "obrigatório para a Geração de Quadros (DLSS 3/4 da NVIDIA e FSR 3 da AMD). Fora isso, o efeito "
        "no FPS costuma ser neutro ou pequeno. Se notar instabilidade, use Desfazer. Requer reiniciar."
    )
    tecnico = f"HKLM\\{CHAVE_GRAPHICS}\\{VALOR} = 2 (mesma opção de Configurações > Sistema > Tela > Gráficos)"
    texto_botao = "Ativar"

    def status(self) -> StatusAjuste:
        hags = analisar_hags(*coletar_hags())
        if hags.suportado is False:
            return StatusAjuste(hags.descricao, "neutro", disponivel=False)
        ligado = hags.valor_registro == LIGADO or bool(hags.ativado)
        nivel = "ok" if ligado else "info"
        return StatusAjuste(hags.descricao, nivel, aplicado=ligado)

    def _aplicar(self, opcoes: set[str] | None) -> Resultado:
        caps, valor = coletar_hags()
        hags = analisar_hags(caps, valor)
        if hags.suportado is False:
            return Resultado(False, "Sua placa de vídeo ou driver não suporta este recurso.")
        if valor == LIGADO or (hags.ativado and valor is None):
            return Resultado(True, "O agendamento de GPU já está ativado.")
        self.estado.guardar_original(self.id, valor)
        registro.gravar_dword(winreg.HKEY_LOCAL_MACHINE, CHAVE_GRAPHICS, VALOR, LIGADO)
        return Resultado(True, "Agendamento de GPU ativado.", requer_reinicio=True)

    def _desfazer(self, original: object) -> Resultado:
        registro.gravar_dword(winreg.HKEY_LOCAL_MACHINE, CHAVE_GRAPHICS, VALOR,
                              None if original is None else int(original))  # type: ignore[arg-type]
        return Resultado(True, "Configuração anterior do agendamento de GPU restaurada.",
                         requer_reinicio=True)
