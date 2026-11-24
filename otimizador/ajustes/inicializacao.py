"""Atalho para a aba Inicialização do Gerenciador de Tarefas."""

from __future__ import annotations

import os
import subprocess

from .base import Ajuste, Resultado, StatusAjuste


class AbrirInicializacao(Ajuste):
    id = "inicializacao"
    titulo = "Programas de inicialização"
    explicacao = (
        "Launchers (Steam, Epic, Battle.net...) e apps de fundo abertos com o Windows deixam o boot "
        "mais lento e ocupam memória. O app não desativa nada sozinho: ele abre a aba Inicialização do "
        "Gerenciador de Tarefas para você escolher. A lista completa está na tela Diagnóstico."
    )
    tecnico = "taskmgr /0 /startup"
    texto_botao = "Abrir Gerenciador de Tarefas"
    repetivel = True
    altera_sistema = False
    reversivel = False

    def status(self) -> StatusAjuste:
        return StatusAjuste("Você decide o que desativar", "neutro")

    def _aplicar(self, opcoes: set[str] | None) -> Resultado:
        try:
            subprocess.Popen(["taskmgr", "/0", "/startup"], creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError:
            os.startfile("ms-settings:startupapps")  # alternativa: Configurações > Aplicativos
            return Resultado(True, "Configurações > Aplicativos > Inicialização aberto.")
        return Resultado(True, "Gerenciador de Tarefas aberto na aba Inicialização.")
