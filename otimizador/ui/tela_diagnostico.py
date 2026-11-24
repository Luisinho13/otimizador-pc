"""Tela de diagnóstico (somente leitura)."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..core.formato import gb, tamanho
from ..diagnostico import Diagnostico, executar_diagnostico
from . import tema
from .componentes import Cartao, Selo, TextoQuebrado, botao, cabecalho_tela
from .tarefas import Executor

ICONES = {"ok": "✔", "info": "●", "aviso": "▲"}


class TelaDiagnostico(ctk.CTkFrame):
    def __init__(self, master: Any, executor: Executor) -> None:
        super().__init__(master, fg_color="transparent")
        self.executor = executor
        self.diagnostico: Diagnostico | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        topo = cabecalho_tela(self, "Diagnóstico", "Informações do hardware e do Windows. Nada é alterado aqui.")
        topo.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        self.botao_atualizar = botao(topo, "Atualizar", self.atualizar, primario=False, largura=110)
        self.botao_atualizar.grid(row=0, column=1, rowspan=2, sticky="e")

        self.conteudo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.conteudo.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 12))
        self.conteudo.grid_columnconfigure((0, 1), weight=1, uniform="col")

    # ------------------------------------------------------------------ carregamento
    def atualizar(self) -> None:
        self.botao_atualizar.configure(state="disabled")
        self._limpar()
        carregando = ctk.CTkFrame(self.conteudo, fg_color="transparent")
        carregando.grid(row=0, column=0, columnspan=2, pady=80)
        ctk.CTkLabel(carregando, text="Coletando informações do sistema...", font=tema.fonte(14),
                     text_color=tema.TEXTO_SECUNDARIO).pack(pady=(0, 12))
        barra = ctk.CTkProgressBar(carregando, mode="indeterminate", width=280)
        barra.pack()
        barra.start()
        self.executor.rodar(executar_diagnostico, self._mostrar, self._falhou)

    def _falhou(self, erro: Exception) -> None:
        self._limpar()
        self.botao_atualizar.configure(state="normal")
        cartao = Cartao(self.conteudo, "Não foi possível concluir o diagnóstico")
        cartao.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        TextoQuebrado(cartao.corpo, str(erro), cor=tema.NIVEIS["erro"]).grid(row=0, column=0, columnspan=2, sticky="w")

    def _limpar(self) -> None:
        for filho in self.conteudo.winfo_children():
            filho.destroy()

    # ------------------------------------------------------------------ exibição
    def _mostrar(self, diag: Diagnostico) -> None:
        self.diagnostico = diag
        self._limpar()
        self.botao_atualizar.configure(state="normal")
        pos = {"padx": 12, "pady": 8, "sticky": "nsew"}

        self._resumo(diag).grid(row=0, column=0, columnspan=2, **pos)
        self._cpu(diag).grid(row=1, column=0, **pos)
        self._gpu(diag).grid(row=1, column=1, **pos)
        self._memoria(diag).grid(row=2, column=0, columnspan=2, **pos)
        self._discos(diag).grid(row=3, column=0, **pos)
        self._windows(diag).grid(row=3, column=1, **pos)
        self._inicializacao(diag).grid(row=4, column=0, columnspan=2, **pos)
        if diag.erros:
            cartao = Cartao(self.conteudo, "Itens que não puderam ser lidos")
            for erro in diag.erros:
                TextoQuebrado(cartao.corpo, erro, 12, tema.TEXTO_SECUNDARIO).grid(
                    row=cartao.proxima_linha(), column=0, columnspan=2, sticky="w")
            cartao.grid(row=5, column=0, columnspan=2, **pos)

    def _resumo(self, diag: Diagnostico) -> Cartao:
        cartao = Cartao(self.conteudo, "Resumo")
        cartao.corpo.grid_columnconfigure(1, weight=1)
        for achado in diag.achados:
            linha = cartao.proxima_linha()
            ctk.CTkLabel(cartao.corpo, text=ICONES.get(achado.nivel, "●"), font=tema.fonte(14, True),
                         text_color=tema.NIVEIS[achado.nivel], width=22, anchor="n").grid(
                row=linha, column=0, sticky="n", padx=(0, 8), pady=(6, 0))
            bloco = ctk.CTkFrame(cartao.corpo, fg_color="transparent")
            bloco.grid(row=linha, column=1, sticky="ew", pady=(4, 6))
            bloco.grid_columnconfigure(0, weight=1)
            TextoQuebrado(bloco, achado.titulo, 14, negrito=True).grid(row=0, column=0, sticky="w")
            TextoQuebrado(bloco, achado.detalhe, 13, tema.TEXTO_SECUNDARIO).grid(row=1, column=0, sticky="w")
        return cartao

    def _cpu(self, diag: Diagnostico) -> Cartao:
        cartao = Cartao(self.conteudo, "Processador")
        if not diag.processadores:
            cartao.linha("Status", "Não detectado")
        for cpu in diag.processadores:
            cartao.linha("Modelo", cpu.nome)
            cartao.linha("Núcleos", f"{cpu.nucleos} núcleos / {cpu.threads} threads")
            cartao.linha("Clock base", f"{cpu.clock_base_mhz / 1000:.1f} GHz".replace(".", ","))
        cartao.linha("Placa-mãe", diag.placa_mae)
        return cartao

    def _gpu(self, diag: Diagnostico) -> Cartao:
        cartao = Cartao(self.conteudo, "Placa de vídeo")
        if not diag.placas_video:
            cartao.linha("Status", "Não detectada")
        for gpu in diag.placas_video:
            cartao.linha("Modelo", gpu.nome)
            driver = gpu.driver
            if gpu.data_driver:
                ano, mes, dia = gpu.data_driver.split("-")
                driver += f"  ({dia}/{mes}/{ano})"
            cartao.linha("Driver", driver)
            if gpu.vram_bytes:
                cartao.linha("Memória", f"{gb(gpu.vram_bytes):.0f} GB")
        return cartao

    def _memoria(self, diag: Diagnostico) -> Cartao:
        mem = diag.memoria
        slots = f"{len(mem.pentes)} de {mem.slots_total} slots" if mem.slots_total else f"{len(mem.pentes)} pente(s)"
        cartao = Cartao(self.conteudo, "Memória RAM", f"{gb(mem.total_bytes):.0f} GB · {slots}")
        cartao.linha("Velocidade atual", f"{mem.mhz_atual} MHz", "aviso" if mem.abaixo_do_anunciado else "ok")
        if mem.mhz_anunciado:
            cartao.linha("Velocidade dos pentes", f"~{mem.mhz_anunciado} MHz (estimada pelo modelo do pente)")
        nivel_canal = {True: "ok", False: "aviso", None: "neutro"}[mem.dual_channel]
        cartao.linha("Canais", mem.canal, nivel_canal)

        if mem.pentes:
            tabela = ctk.CTkFrame(cartao.corpo, fg_color="transparent")
            tabela.grid(row=cartao.proxima_linha(), column=0, columnspan=2, sticky="ew", pady=(10, 0))
            colunas = ("Slot", "Canal", "Capacidade", "Fabricante", "Modelo", "Atual", "Anunciada")
            for c, titulo in enumerate(colunas):
                tabela.grid_columnconfigure(c, weight=1)
                ctk.CTkLabel(tabela, text=titulo, font=tema.fonte(12, True), text_color=tema.TEXTO_SECUNDARIO,
                             anchor="w").grid(row=0, column=c, sticky="w", padx=(0, 12))
            for r, p in enumerate(mem.pentes, start=1):
                valores = (p.slot, p.canal or "?", f"{gb(p.capacidade_bytes):.0f} GB", p.fabricante or "—",
                           p.modelo or "—", f"{p.mhz_atual} MHz",
                           f"~{p.mhz_anunciado} MHz" if p.mhz_anunciado else "—")
                for c, valor in enumerate(valores):
                    ctk.CTkLabel(tabela, text=valor, font=tema.fonte(12), text_color=tema.TEXTO,
                                 anchor="w").grid(row=r, column=c, sticky="w", padx=(0, 12))
        return cartao

    def _discos(self, diag: Diagnostico) -> Cartao:
        cartao = Cartao(self.conteudo, "Armazenamento")
        cartao.corpo.grid_columnconfigure(0, weight=1)
        if not diag.discos:
            cartao.linha("Status", "Nenhum disco detectado")
        for disco in diag.discos:
            linha = cartao.proxima_linha()
            topo = ctk.CTkFrame(cartao.corpo, fg_color="transparent")
            topo.grid(row=linha, column=0, columnspan=2, sticky="ew", pady=(8, 2))
            ctk.CTkLabel(topo, text=disco.nome, font=tema.fonte(13, True), text_color=tema.TEXTO).pack(side="left")
            Selo(topo, disco.tipo, "ok" if disco.eh_ssd else "neutro").pack(side="left", padx=8)
            ctk.CTkLabel(topo, text=tamanho(disco.tamanho_bytes), font=tema.fonte(12),
                         text_color=tema.TEXTO_SECUNDARIO).pack(side="right")
            for vol in disco.volumes:
                usado = 1 - vol.pct_livre / 100
                linha = cartao.proxima_linha()
                texto = f"{vol.letra}:  {tamanho(vol.livre_bytes)} livres de {tamanho(vol.total_bytes)}"
                ctk.CTkLabel(cartao.corpo, text=texto, font=tema.fonte(12), text_color=tema.TEXTO_SECUNDARIO,
                             anchor="w").grid(row=linha, column=0, columnspan=2, sticky="w")
                cor = tema.NIVEIS["aviso"] if vol.pct_livre < 10 else tema.DESTAQUE
                barra = ctk.CTkProgressBar(cartao.corpo, height=8, progress_color=cor, fg_color=tema.BORDA)
                barra.set(usado)
                barra.grid(row=cartao.proxima_linha(), column=0, columnspan=2, sticky="ew", pady=(2, 4))
        return cartao

    def _windows(self, diag: Diagnostico) -> Cartao:
        cartao = Cartao(self.conteudo, "Windows")
        cartao.linha("Sistema", diag.sistema_operacional)
        ativo = diag.plano_ativo
        cartao.linha("Plano de energia", ativo.nome if ativo else "Desconhecido",
                     "ok" if ativo and ativo.eh_alto_desempenho else "info")
        cartao.linha("Modo de Jogo", diag.modo_jogo.descricao, "ok" if diag.modo_jogo.ativado else "info")
        hags = diag.agendamento_gpu
        cartao.linha("Agendamento de GPU", hags.descricao,
                     "ok" if hags.ativado else ("neutro" if hags.suportado is False else "info"))
        if diag.trim_ativo is None:
            cartao.linha("TRIM", "Desconhecido", "neutro")
        else:
            cartao.linha("TRIM", "Ativado" if diag.trim_ativo else "Desativado",
                         "ok" if diag.trim_ativo else ("aviso" if diag.tem_ssd else "neutro"))
        return cartao

    def _inicializacao(self, diag: Diagnostico) -> Cartao:
        ativos = sum(p.ativo is not False for p in diag.inicializacao)
        cartao = Cartao(self.conteudo, "Programas de inicialização",
                        f"{ativos} ativo(s) de {len(diag.inicializacao)}")
        if not diag.inicializacao:
            cartao.linha("Status", "Nenhum programa encontrado")
            return cartao
        tabela = ctk.CTkFrame(cartao.corpo, fg_color="transparent")
        tabela.grid(row=0, column=0, columnspan=2, sticky="ew")
        for c, peso in enumerate((3, 3, 2, 1)):
            tabela.grid_columnconfigure(c, weight=peso)
        for c, titulo in enumerate(("Nome", "Programa", "Para", "Status")):
            ctk.CTkLabel(tabela, text=titulo, font=tema.fonte(12, True), text_color=tema.TEXTO_SECUNDARIO,
                         anchor="w").grid(row=0, column=c, sticky="w", padx=(0, 12), pady=(0, 4))
        for r, prog in enumerate(diag.inicializacao, start=1):
            for c, valor in enumerate((prog.nome, prog.executavel, prog.escopo)):
                ctk.CTkLabel(tabela, text=valor, font=tema.fonte(12), text_color=tema.TEXTO,
                             anchor="w").grid(row=r, column=c, sticky="w", padx=(0, 12), pady=1)
            if prog.ativo is None:
                selo = Selo(tabela, "Outro", "neutro")
            else:
                selo = Selo(tabela, "Ativo" if prog.ativo else "Desativado", "info" if prog.ativo else "neutro")
            selo.grid(row=r, column=3, sticky="w", pady=1)
        TextoQuebrado(cartao.corpo, "Apps da Microsoft Store e tarefas agendadas aparecem só no Gerenciador "
                      "de Tarefas. Para desativar algum, use a tela Ajustes.", 12, tema.TEXTO_SECUNDARIO).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        return cartao
