"""Modo de Jogo do Windows."""

from __future__ import annotations

import winreg

from ..core import registro
from ..diagnostico.coleta import CHAVE_GAMEBAR, coletar_modo_jogo
from ..diagnostico.sistema import analisar_modo_jogo
from .base import Ajuste, Resultado, StatusAjuste

VALOR = "AutoGameModeEnabled"


class ModoDeJogo(Ajuste):
    id = "modo_jogo"
    titulo = "Modo de Jogo"
    explicacao = (
        "Quando um jogo está aberto, o Windows dá prioridade a ele e adia atualizações e notificações "
        "de instalação de drivers. Vem ligado por padrão; é a mesma opção de Configurações > Jogos > "
        "Modo de Jogo."
    )
    tecnico = f"HKCU\\{CHAVE_GAMEBAR}\\{VALOR} = 1"
    texto_botao = "Ativar"

    def status(self) -> StatusAjuste:
        modo = analisar_modo_jogo(coletar_modo_jogo())
        return StatusAjuste(modo.descricao, "ok" if modo.ativado else "info", aplicado=modo.ativado)

    def _aplicar(self, opcoes: set[str] | None) -> Resultado:
        atual = coletar_modo_jogo()
        if analisar_modo_jogo(atual).ativado:
            return Resultado(True, "O Modo de Jogo já está ativado.")
        self.estado.guardar_original(self.id, atual)
        registro.gravar_dword(winreg.HKEY_CURRENT_USER, CHAVE_GAMEBAR, VALOR, 1)
        return Resultado(True, "Modo de Jogo ativado.")

    def _desfazer(self, original: object) -> Resultado:
        registro.gravar_dword(winreg.HKEY_CURRENT_USER, CHAVE_GAMEBAR, VALOR,
                              None if original is None else int(original))  # type: ignore[arg-type]
        return Resultado(True, "Configuração anterior do Modo de Jogo restaurada.")
