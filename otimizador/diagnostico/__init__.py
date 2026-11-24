"""Diagnóstico do PC (somente leitura): reúne a coleta, a interpretação e as recomendações."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from . import coleta
from .hardware import (Disco, Memoria, PlacaVideo, Processador, analisar_cpu, analisar_discos,
                       analisar_gpu, analisar_memoria)
from .sistema import (AgendamentoGpu, ModoJogo, PlanoEnergia, ProgramaInicializacao,
                      analisar_hags, analisar_inicializacao, analisar_modo_jogo, analisar_planos,
                      analisar_trim, plano_ativo)

log = logging.getLogger("otimizador.diagnostico")


@dataclass
class Achado:
    nivel: str  # "ok" | "info" | "aviso"
    titulo: str
    detalhe: str


@dataclass
class Diagnostico:
    sistema_operacional: str
    placa_mae: str
    processadores: list[Processador]
    placas_video: list[PlacaVideo]
    memoria: Memoria
    discos: list[Disco]
    planos_energia: list[PlanoEnergia]
    trim_ativo: bool | None
    modo_jogo: ModoJogo
    agendamento_gpu: AgendamentoGpu
    inicializacao: list[ProgramaInicializacao]
    erros: list[str] = field(default_factory=list)
    achados: list[Achado] = field(default_factory=list)

    @property
    def plano_ativo(self) -> PlanoEnergia | None:
        return plano_ativo(self.planos_energia)

    @property
    def tem_ssd(self) -> bool:
        return any(d.eh_ssd for d in self.discos)


def _texto(obj: Any, *campos: str) -> str:
    if not isinstance(obj, dict):
        return "Desconhecido"
    return " ".join(str(obj.get(c) or "").strip() for c in campos).strip() or "Desconhecido"


def montar_diagnostico(brutos: dict[str, Any], erros: list[str] | None = None,
                       hoje: date | None = None) -> Diagnostico:
    """Transforma os dados brutos da coleta no diagnóstico (função pura, testável)."""
    cim = brutos.get("cim") or {}
    caps, hwsch = brutos.get("hags") or (None, None)
    diag = Diagnostico(
        sistema_operacional=_texto(cim.get("so"), "Caption")
        + (f" (build {cim['so']['BuildNumber']})" if isinstance(cim.get("so"), dict) else ""),
        placa_mae=_texto(cim.get("placa_mae"), "Manufacturer", "Product"),
        processadores=analisar_cpu(cim.get("cpu")),
        placas_video=analisar_gpu(cim.get("gpu"), cim.get("gpu_vram"), brutos.get("nvidia_smi") or []),
        memoria=analisar_memoria(cim.get("ram"), cim.get("ram_slots")),
        discos=analisar_discos(cim.get("discos"), cim.get("particoes"), cim.get("volumes")),
        planos_energia=analisar_planos(brutos.get("planos") or ""),
        trim_ativo=analisar_trim(brutos.get("trim") or ""),
        modo_jogo=analisar_modo_jogo(brutos.get("modo_jogo")),
        agendamento_gpu=analisar_hags(caps, hwsch),
        inicializacao=analisar_inicializacao(cim.get("inicializacao"), brutos.get("aprovados") or {}),
        erros=list(erros or []),
    )
    diag.achados = gerar_achados(diag, hoje or date.today())
    return diag


def gerar_achados(d: Diagnostico, hoje: date) -> list[Achado]:
    achados: list[Achado] = []
    mem = d.memoria

    if mem.abaixo_do_anunciado and mem.modelos_misturados:
        # Com pentes diferentes o XMP/DOCP costuma falhar (às vezes o PC nem dá vídeo),
        # então a recomendação útil é trocar os pentes, não mexer na BIOS.
        achados.append(Achado(
            "aviso", "Memória abaixo da velocidade dos pentes",
            f"A RAM está rodando a {mem.mhz_atual} MHz, mas os pentes são de cerca de "
            f"{mem.mhz_anunciado} MHz (estimado pelo modelo). Como são pentes de modelos diferentes, "
            "o XMP/DOCP costuma não funcionar (o PC pode nem dar vídeo). Para usar a velocidade "
            "total, troque por um kit de 2 pentes iguais (mesmo modelo, de preferência vendidos juntos).",
        ))
    elif mem.abaixo_do_anunciado:
        achados.append(Achado(
            "aviso", "Memória abaixo da velocidade dos pentes",
            f"A RAM está rodando a {mem.mhz_atual} MHz, mas os pentes são de cerca de "
            f"{mem.mhz_anunciado} MHz (estimado pelo modelo). Ative o perfil XMP (Intel) ou "
            "DOCP/EXPO (AMD) na BIOS. Em placas e processadores de entrada a velocidade máxima "
            "pode ser limitada pelo fabricante; confira o manual.",
        ))
    if mem.dual_channel is False:
        achados.append(Achado(
            "aviso", "Memória em single channel",
            "Dois pentes iguais em canais diferentes (dual channel) costumam aumentar o FPS mínimo "
            "em jogos. Confira no manual da placa-mãe quais slots usar (geralmente A2 e B2).",
        ))
    if mem.modelos_misturados and not mem.abaixo_do_anunciado:
        achados.append(Achado(
            "info", "Pentes de modelos diferentes",
            "Funciona, mas pentes diferentes podem não ficar estáveis com XMP/DOCP. "
            "Se ativar, teste com calma antes de confiar no sistema.",
        ))

    for disco in d.discos:
        for vol in disco.volumes:
            if vol.total_bytes and vol.pct_livre < 10:
                achados.append(Achado(
                    "aviso", f"Pouco espaço livre em {vol.letra}:",
                    f"Restam {vol.pct_livre:.0f}%. Deixe pelo menos 10–15% livre; SSDs quase cheios "
                    "ficam mais lentos e o Windows precisa de espaço para atualizações.",
                ))
        if not disco.eh_ssd and disco.tipo == "HDD" and any(v.letra == "C" for v in disco.volumes):
            achados.append(Achado(
                "aviso", "Windows instalado em HD",
                "O Windows está em um disco mecânico. Migrar para um SSD é a melhoria mais perceptível "
                "em tempo de boot e carregamento.",
            ))

    if d.tem_ssd and d.trim_ativo is False:
        achados.append(Achado("aviso", "TRIM desativado",
                              "Seus SSDs não estão recebendo TRIM. Veja o ajuste na aba Ajustes."))

    ativo = d.plano_ativo
    if ativo and not ativo.eh_alto_desempenho:
        achados.append(Achado(
            "info", f"Plano de energia: {ativo.nome}",
            "Em desktop, o Alto desempenho evita que o processador reduza o clock. O ganho em jogos "
            "costuma ser pequeno, mas pode reduzir engasgos. Veja a aba Ajustes.",
        ))
    if not d.modo_jogo.ativado:
        achados.append(Achado("info", "Modo de Jogo desativado",
                              "O Modo de Jogo dá prioridade ao jogo e adia atualizações durante a partida."))

    gpu = d.agendamento_gpu
    if gpu.suportado and not gpu.ativado and not gpu.pendente_reinicio:
        achados.append(Achado("info", "Agendamento de GPU desativado",
                              "Sua placa suporta o agendamento de GPU acelerado por hardware. "
                              "Ele é necessário para a Geração de Quadros (DLSS 3/4 e FSR 3)."))
    if gpu.pendente_reinicio:
        achados.append(Achado("info", "Reinicialização pendente",
                              "O agendamento de GPU foi alterado e só passa a valer após reiniciar."))

    for placa in d.placas_video:
        if placa.data_driver:
            try:
                idade = (hoje - date.fromisoformat(placa.data_driver)).days
            except ValueError:
                continue
            if idade > 180:
                achados.append(Achado(
                    "info", f"Driver de vídeo com {idade // 30} meses",
                    f"O driver da {placa.nome} é de {date.fromisoformat(placa.data_driver):%d/%m/%Y}. "
                    "Drivers novos costumam trazer otimizações para jogos recentes.",
                ))

    ativos = [p for p in d.inicializacao if p.ativo is not False]
    if len(ativos) >= 8:
        achados.append(Achado(
            "info", f"{len(ativos)} programas abrem com o Windows",
            "Launchers e apps em segundo plano deixam o boot mais lento e ocupam memória. "
            "Desative os que não precisa na aba Inicialização do Gerenciador de Tarefas.",
        ))

    if not any(a.nivel == "aviso" for a in achados):
        achados.insert(0, Achado("ok", "Nenhum problema importante encontrado",
                                 "As sugestões abaixo, se houver, são opcionais."))
    return achados


def executar_diagnostico() -> Diagnostico:
    """Coleta tudo em paralelo (somente leitura) e monta o diagnóstico."""
    log.info("Iniciando diagnóstico...")
    tarefas: dict[str, Callable[[], Any]] = {
        "cim": coleta.coletar_cim,
        "nvidia_smi": coleta.coletar_nvidia_smi,
        "planos": coleta.coletar_planos,
        "trim": coleta.coletar_trim,
        "modo_jogo": coleta.coletar_modo_jogo,
        "hags": coleta.coletar_hags,
        "aprovados": coleta.coletar_inicializacao_aprovada,
    }
    brutos: dict[str, Any] = {}
    erros: list[str] = []
    with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
        futuros = {nome: pool.submit(funcao) for nome, funcao in tarefas.items()}
        for nome, futuro in futuros.items():
            try:
                brutos[nome] = futuro.result()
            except Exception as erro:  # noqa: BLE001 - uma falha não pode derrubar o resto
                log.warning("Falha ao coletar '%s': %s", nome, erro)
                erros.append(f"{nome}: {erro}")

    diag = montar_diagnostico(brutos, erros)
    for achado in diag.achados:
        log.info("  [%s] %s", achado.nivel, achado.titulo)
    log.info("Diagnóstico concluído: %d sugestão(ões).", sum(a.nivel != "ok" for a in diag.achados))
    return diag
