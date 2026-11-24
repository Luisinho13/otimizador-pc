"""Janela principal: navegação lateral, telas e o fluxo do ponto de restauração."""

from __future__ import annotations

import logging
import os
import queue
import sys
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk

from .. import APP_NOME, __version__
from ..ajustes import criar_ajustes
from ..core import restauracao
from ..core.estado import Estado
from ..core.log import pasta_logs
from . import tema
from .componentes import Selo, botao
from .tarefas import Executor
from .tela_ajustes import TelaAjustes
from .tela_diagnostico import TelaDiagnostico
from .tela_log import TelaLog

log = logging.getLogger("otimizador.ui")


def recurso(caminho: str) -> Path:
    """Caminho de um arquivo empacotado (funciona no código-fonte e no .exe do PyInstaller)."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])
    return Path(base) / caminho


class App(ctk.CTk):
    def __init__(self, admin: bool, arquivo_log: Path, fila_log: queue.Queue[str]) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=tema.FUNDO)
        self.admin = admin
        self.diagnostico_desatualizado = False
        self._ponto_resolvido = False
        self.executor = Executor(self)
        self.report_callback_exception = self._erro_inesperado

        self.title(f"{APP_NOME} {__version__}")
        self._centralizar(1200, 780)
        self.minsize(980, 640)
        icone = recurso("assets/icone.ico")
        if icone.exists():
            # O CustomTkinter define o próprio ícone ~200 ms após abrir; aplicamos o nosso depois.
            self.after(300, lambda: self.iconbitmap(str(icone)))

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._montar_lateral()

        area = ctk.CTkFrame(self, fg_color="transparent")
        area.grid(row=0, column=1, sticky="nsew")
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(0, weight=1)
        self.telas: dict[str, ctk.CTkFrame] = {
            "diagnostico": TelaDiagnostico(area, self.executor),
            "ajustes": TelaAjustes(area, self, criar_ajustes(Estado())),
            "log": TelaLog(area, fila_log, arquivo_log),
        }
        for tela in self.telas.values():
            tela.grid(row=0, column=0, sticky="nsew")

        self.mostrar("diagnostico")
        self.after(100, self._carregar_inicial)

    # ---------------------------------------------------------------- layout
    def _centralizar(self, largura: int, altura: int) -> None:
        escala = self._get_window_scaling()
        tela_l, tela_a = self.winfo_screenwidth() / escala, self.winfo_screenheight() / escala
        largura, altura = min(largura, int(tela_l * 0.92)), min(altura, int(tela_a * 0.88))
        x, y = int((tela_l - largura) / 2), int((tela_a - altura) / 2.4)
        self.geometry(f"{largura}x{altura}+{max(x, 0)}+{max(y, 0)}")

    def _montar_lateral(self) -> None:
        lateral = ctk.CTkFrame(self, fg_color=tema.LATERAL, corner_radius=0, width=230)
        lateral.grid(row=0, column=0, sticky="nsw")
        lateral.grid_propagate(False)
        lateral.grid_columnconfigure(0, weight=1)
        lateral.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(lateral, text="⚡ Otimizador", font=tema.fonte(22, True), text_color=tema.TEXTO,
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=22, pady=(26, 0))
        ctk.CTkLabel(lateral, text=f"de PC  ·  v{__version__}", font=tema.fonte(12),
                     text_color=tema.TEXTO_SECUNDARIO, anchor="w").grid(row=1, column=0, sticky="ew", padx=24)

        self.botoes_nav: dict[str, ctk.CTkButton] = {}
        for i, (chave, texto) in enumerate((("diagnostico", "Diagnóstico"), ("ajustes", "Ajustes"),
                                            ("log", "Log"))):
            b = ctk.CTkButton(lateral, text=texto, anchor="w", height=40, corner_radius=8,
                              font=tema.fonte(14, True), fg_color="transparent", text_color=tema.TEXTO,
                              hover_color=tema.SECUNDARIO_HOVER, command=lambda c=chave: self.mostrar(c))
            b.grid(row=2 + i, column=0, sticky="ew", padx=14, pady=(28 if i == 0 else 4, 0))
            self.botoes_nav[chave] = b

        rodape = ctk.CTkFrame(lateral, fg_color="transparent")
        rodape.grid(row=6, column=0, sticky="sew", padx=20, pady=20)
        rodape.grid_columnconfigure(0, weight=1)
        Selo(rodape, "Administrador" if self.admin else "Somente leitura",
             "ok" if self.admin else "aviso").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(rodape, text="Ponto de restauração", font=tema.fonte(12, True),
                     text_color=tema.TEXTO_SECUNDARIO, anchor="w").grid(row=1, column=0, sticky="w", pady=(14, 0))
        self.rotulo_ponto = ctk.CTkLabel(rodape, text="Será criado antes do 1º ajuste", font=tema.fonte(12),
                                         text_color=tema.TEXTO, anchor="w", justify="left", wraplength=190)
        self.rotulo_ponto.grid(row=2, column=0, sticky="w")
        botao(rodape, "Pasta de logs", lambda: os.startfile(pasta_logs()), primario=False, largura=190).grid(
            row=3, column=0, sticky="ew", pady=(16, 0))

    def mostrar(self, chave: str) -> None:
        for nome, b in self.botoes_nav.items():
            b.configure(fg_color=tema.SECUNDARIO if nome == chave else "transparent")
        self.telas[chave].tkraise()
        if chave == "diagnostico" and self.diagnostico_desatualizado:
            self.diagnostico_desatualizado = False
            self.telas["diagnostico"].atualizar()  # type: ignore[attr-defined]

    def _carregar_inicial(self) -> None:
        self.telas["diagnostico"].atualizar()  # type: ignore[attr-defined]
        self.telas["ajustes"].atualizar_todos()  # type: ignore[attr-defined]

    # ---------------------------------------------------------------- ponto de restauração
    def garantir_ponto_restauracao(self, continuar: Callable[[], None], cancelar: Callable[[], None]) -> None:
        """Garante um ponto de restauração antes da primeira alteração da sessão."""
        if self._ponto_resolvido:
            continuar()
            return
        self.rotulo_ponto.configure(text="Criando... (pode levar alguns minutos)")
        self.executor.rodar(restauracao.criar_ponto,
                            lambda r: self._ponto_criado(r, continuar, cancelar, tentou_ativar=False),
                            lambda erro: self._sem_ponto(str(erro), continuar, cancelar))

    def _ponto_criado(self, r: restauracao.ResultadoRestauracao, continuar: Callable[[], None],
                      cancelar: Callable[[], None], tentou_ativar: bool) -> None:
        if r.protegido and r.ponto:
            self._ponto_resolvido = True
            prefixo = "Criado em" if r.status == "criado" else "Usando o de"
            self.rotulo_ponto.configure(text=f"{prefixo} {r.ponto.data:%d/%m %H:%M}", text_color=tema.NIVEIS["ok"])
            continuar()
            return

        if r.status == "desativado" and not tentou_ativar:
            ativar = messagebox.askyesno(
                "Proteção do Sistema desativada",
                "A Proteção do Sistema (que guarda os pontos de restauração) está desativada.\n\n"
                "Deseja ativá-la na unidade do Windows e criar o ponto agora? Ela reserva um pouco "
                "de espaço em disco para os pontos de restauração.", parent=self)
            if ativar:
                self.rotulo_ponto.configure(text="Ativando a Proteção do Sistema...")

                def ativar_e_criar() -> restauracao.ResultadoRestauracao:
                    restauracao.ativar_protecao()
                    return restauracao.criar_ponto()

                self.executor.rodar(ativar_e_criar,
                                    lambda r2: self._ponto_criado(r2, continuar, cancelar, tentou_ativar=True),
                                    lambda erro: self._sem_ponto(str(erro), continuar, cancelar))
                return
        self._sem_ponto(r.mensagem, continuar, cancelar)

    def _sem_ponto(self, motivo: str, continuar: Callable[[], None], cancelar: Callable[[], None]) -> None:
        log.warning("Sem ponto de restauração: %s", motivo)
        self.rotulo_ponto.configure(text="Não criado", text_color=tema.NIVEIS["aviso"])
        seguir = messagebox.askyesno(
            "Sem ponto de restauração",
            f"{motivo}\n\nDeseja continuar mesmo assim? Os ajustes deste app podem ser revertidos "
            "pelo botão Desfazer.", icon="warning", parent=self)
        if seguir:
            log.warning("O usuário optou por continuar sem ponto de restauração.")
            self._ponto_resolvido = True
            continuar()
        else:
            self.rotulo_ponto.configure(text="Será criado antes do 1º ajuste", text_color=tema.TEXTO)
            cancelar()

    # ---------------------------------------------------------------- erros
    def _erro_inesperado(self, tipo: type[BaseException], valor: BaseException, tb: Any) -> None:
        log.error("Erro inesperado na interface", exc_info=(tipo, valor, tb))
        messagebox.showerror("Erro inesperado", f"{valor}\n\nDetalhes foram salvos no log.", parent=self)
