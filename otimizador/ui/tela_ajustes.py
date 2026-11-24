"""Tela de ajustes: um cartão por ajuste, com explicação, status e botões."""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..ajustes import Ajuste, Resultado, StatusAjuste
from . import tema
from .componentes import Cartao, Selo, TextoQuebrado, botao, cabecalho_tela

if TYPE_CHECKING:
    from .app import App


class CartaoAjuste(Cartao):
    def __init__(self, master: Any, ajuste: Ajuste, tela: TelaAjustes) -> None:
        super().__init__(master, ajuste.titulo)
        self.ajuste = ajuste
        self.tela = tela
        self.status: StatusAjuste | None = None
        self.caixas: dict[str, ctk.CTkCheckBox] = {}
        self.ultimo_resultado: Resultado | None = None

        self.selo = Selo(self.cabecalho, "Verificando...", "neutro")
        self.selo.grid(row=0, column=1, sticky="e")

        self.corpo.grid_columnconfigure(0, weight=1)
        TextoQuebrado(self.corpo, ajuste.explicacao, 13, tema.TEXTO).grid(row=0, column=0, sticky="w")
        TextoQuebrado(self.corpo, f"Como funciona: {ajuste.tecnico}", 12, tema.TEXTO_SECUNDARIO).grid(
            row=1, column=0, sticky="w", pady=(6, 0))

        self.quadro_opcoes = ctk.CTkFrame(self.corpo, fg_color="transparent")
        self.quadro_opcoes.grid(row=2, column=0, sticky="ew")
        self.quadro_opcoes.grid_remove()  # um CTkFrame vazio ocuparia 200 px de altura

        rodape = ctk.CTkFrame(self.corpo, fg_color="transparent")
        rodape.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        rodape.grid_columnconfigure(2, weight=1)
        self.botao_aplicar = botao(rodape, ajuste.texto_botao, lambda: tela.aplicar(self), largura=170)
        self.botao_aplicar.grid(row=0, column=0, sticky="w")
        self.botao_desfazer = None
        if ajuste.reversivel:
            self.botao_desfazer = botao(rodape, "Desfazer", lambda: tela.desfazer(self), primario=False, largura=110)
            self.botao_desfazer.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.mensagem = ctk.CTkLabel(rodape, text="", font=tema.fonte(12), text_color=tema.TEXTO_SECUNDARIO,
                                     anchor="w")
        self.mensagem.grid(row=0, column=2, sticky="w", padx=(14, 0))

    # ---------------------------------------------------------------- estado visual
    def ocupado(self, texto: str) -> None:
        self.botao_aplicar.configure(state="disabled")
        if self.botao_desfazer:
            self.botao_desfazer.configure(state="disabled")
        self.mensagem.configure(text=texto, text_color=tema.TEXTO_SECUNDARIO)

    def mostrar_status(self, status: StatusAjuste) -> None:
        self.status = status
        self.selo.atualizar(status.texto, status.nivel)
        self._montar_opcoes(status)

        bloqueado_sem_admin = self.ajuste.altera_sistema and not self.tela.app.admin
        if bloqueado_sem_admin:
            self.botao_aplicar.configure(state="disabled", text=self.ajuste.texto_botao)
            self.mensagem.configure(text="Requer administrador", text_color=tema.NIVEIS["aviso"])
        elif not status.disponivel:
            self.botao_aplicar.configure(state="disabled", text=self.ajuste.texto_botao)
            self.mensagem.configure(text="Não disponível neste PC", text_color=tema.TEXTO_SECUNDARIO)
        elif status.aplicado and not self.ajuste.repetivel:
            self.botao_aplicar.configure(state="disabled", text="✔ Já aplicado", fg_color=tema.SECUNDARIO)
            self.mensagem.configure(text="")
        else:
            self.botao_aplicar.configure(state="normal", text=self.ajuste.texto_botao, fg_color=tema.DESTAQUE)
            self.mensagem.configure(text="")

        if self.botao_desfazer:
            pode = self.ajuste.pode_desfazer() and self.tela.app.admin
            self.botao_desfazer.configure(state="normal" if pode else "disabled")
        if self.ultimo_resultado and not bloqueado_sem_admin:
            self.mostrar_resultado(self.ultimo_resultado)

    def mostrar_resultado(self, resultado: Resultado) -> None:
        cor = tema.NIVEIS["ok"] if resultado.sucesso else tema.NIVEIS["erro"]
        texto = ("✔ " if resultado.sucesso else "✖ ") + resultado.mensagem
        if resultado.requer_reinicio:
            texto += " Reinicie o PC."
        self.mensagem.configure(text=texto[:140], text_color=cor)

    def _montar_opcoes(self, status: StatusAjuste) -> None:
        for filho in self.quadro_opcoes.winfo_children():
            filho.destroy()
        self.caixas.clear()
        if status.opcoes:
            self.quadro_opcoes.grid()
        else:
            self.quadro_opcoes.grid_remove()
        for i, opcao in enumerate(status.opcoes):
            caixa = ctk.CTkCheckBox(self.quadro_opcoes, text=f"{opcao.rotulo}   —   {opcao.detalhe}",
                                    font=tema.fonte(13), text_color=tema.TEXTO, checkbox_width=20,
                                    checkbox_height=20, corner_radius=5)
            if opcao.marcada:
                caixa.select()
            caixa.grid(row=i, column=0, sticky="w", pady=(10 if i == 0 else 3, 0))
            self.caixas[opcao.id] = caixa

    def opcoes_marcadas(self) -> set[str] | None:
        if not self.caixas:
            return None
        return {id_ for id_, caixa in self.caixas.items() if caixa.get()}

    def rotulos_marcados(self) -> list[str]:
        assert self.status is not None
        marcadas = self.opcoes_marcadas() or set()
        return [f"• {o.rotulo} ({o.detalhe.split(' · ')[0]})" for o in self.status.opcoes if o.id in marcadas]


class TelaAjustes(ctk.CTkFrame):
    def __init__(self, master: Any, app: App, ajustes: list[Ajuste]) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        topo = cabecalho_tela(self, "Ajustes", "Nada é aplicado automaticamente. Antes da primeira alteração "
                                               "é criado um ponto de restauração.")
        topo.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        botao(topo, "Verificar de novo", self.atualizar_todos, primario=False, largura=140).grid(
            row=0, column=1, rowspan=2, sticky="e")

        self.lista = lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        lista.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 12))
        lista.grid_columnconfigure(0, weight=1)
        self.cartoes = [CartaoAjuste(lista, ajuste, self) for ajuste in ajustes]
        for i, cartao in enumerate(self.cartoes):
            cartao.grid(row=i, column=0, sticky="ew", padx=12, pady=8)

    @property
    def _janela(self) -> Any:
        return self.winfo_toplevel()

    def atualizar_todos(self) -> None:
        for cartao in self.cartoes:
            self.atualizar(cartao)

    def atualizar(self, cartao: CartaoAjuste) -> None:
        cartao.ocupado("Verificando...")
        self.app.executor.rodar(
            cartao.ajuste.verificar, cartao.mostrar_status,
            lambda erro: cartao.mostrar_status(StatusAjuste(f"Erro: {erro}", "erro", disponivel=False)),
        )

    # ---------------------------------------------------------------- aplicar / desfazer
    def aplicar(self, cartao: CartaoAjuste) -> None:
        ajuste = cartao.ajuste
        cartao.ultimo_resultado = None
        opcoes = cartao.opcoes_marcadas()
        if opcoes is not None and not opcoes:
            messagebox.showwarning("Nada selecionado", "Marque pelo menos um item.", parent=self._janela)
            return

        if opcoes is not None:
            pergunta = ("Os arquivos destes itens serão apagados (não dá para desfazer):\n\n"
                        + "\n".join(cartao.rotulos_marcados()) + "\n\nContinuar?")
        elif ajuste.altera_sistema:
            pergunta = f"Aplicar \"{ajuste.titulo}\"?\n\nO que será feito:\n{ajuste.tecnico}"
        else:
            pergunta = None
        if pergunta and not messagebox.askyesno("Confirmar", pergunta, parent=self._janela):
            return

        def executar() -> None:
            cartao.ocupado("Aplicando... (pode levar alguns minutos)" if ajuste.id == "trim" else "Aplicando...")
            self.app.executor.rodar(lambda: ajuste.aplicar(opcoes), lambda r: self._concluido(cartao, r))

        if ajuste.altera_sistema:
            cartao.ocupado("Preparando ponto de restauração...")
            self.app.garantir_ponto_restauracao(executar, cancelar=lambda: self.atualizar(cartao))
        else:
            executar()

    def desfazer(self, cartao: CartaoAjuste) -> None:
        if not messagebox.askyesno("Desfazer", f"Voltar \"{cartao.ajuste.titulo}\" para como estava antes?",
                                   parent=self._janela):
            return
        cartao.ultimo_resultado = None
        cartao.ocupado("Desfazendo...")
        self.app.executor.rodar(cartao.ajuste.desfazer, lambda r: self._concluido(cartao, r))

    def _concluido(self, cartao: CartaoAjuste, resultado: Resultado) -> None:
        self.app.diagnostico_desatualizado = True
        cartao.ultimo_resultado = resultado
        self.atualizar(cartao)
        if not resultado.sucesso:
            messagebox.showerror("Não foi possível concluir", resultado.mensagem, parent=self._janela)
        elif resultado.requer_reinicio:
            messagebox.showinfo("Reinicialização necessária",
                                f"{resultado.mensagem}\n\nReinicie o computador para a alteração ter efeito.",
                                parent=self._janela)
