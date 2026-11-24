"""Limpeza de arquivos temporários e caches de shaders."""

from __future__ import annotations

import logging
import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core.formato import tamanho
from .base import Ajuste, Opcao, Resultado, StatusAjuste

log = logging.getLogger("otimizador.limpeza")

UM_DIA = 24 * 3600


@dataclass
class AlvoLimpeza:
    id: str
    nome: str
    pastas: list[Path]
    idade_minima_s: int = 0  # arquivos mais novos que isso são preservados

    @property
    def existentes(self) -> list[Path]:
        return [p for p in self.pastas if p.is_dir()]


@dataclass
class Medicao:
    bytes: int = 0
    arquivos: int = 0


@dataclass
class ResultadoLimpeza:
    liberado: int = 0
    apagados: int = 0
    em_uso: int = 0
    erros: list[str] = field(default_factory=list)


def _env(nome: str, padrao: str = "") -> Path:
    return Path(os.environ.get(nome, padrao))


def alvos_padrao() -> list[AlvoLimpeza]:
    local = _env("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    local_low = local.parent / "LocalLow"
    windir = _env("SystemRoot", r"C:\Windows")
    return [
        AlvoLimpeza("temp_usuario", "Temporários do usuário (%TEMP%)", [_env("TEMP", str(local / "Temp"))],
                    idade_minima_s=UM_DIA),
        AlvoLimpeza("temp_windows", "Temporários do Windows", [windir / "Temp"], idade_minima_s=UM_DIA),
        AlvoLimpeza("cache_directx", "Cache de shaders do DirectX", [local / "D3DSCache"]),
        AlvoLimpeza("cache_nvidia", "Cache de shaders da NVIDIA", [
            local / "NVIDIA" / "DXCache", local / "NVIDIA" / "GLCache",
            local_low / "NVIDIA" / "DXCache", local_low / "NVIDIA" / "GLCache",  # drivers recentes
            local / "NVIDIA Corporation" / "NV_Cache",  # drivers antigos
            local_low / "NVIDIA" / "PerDriverVersion" / "DXCache",
            local_low / "NVIDIA" / "PerDriverVersion" / "GLCache",
        ]),
        AlvoLimpeza("cache_amd", "Cache de shaders da AMD", [
            local / "AMD" / "DxCache", local / "AMD" / "DxcCache",
            local / "AMD" / "GLCache", local / "AMD" / "VkCache",
        ]),
        AlvoLimpeza("cache_intel", "Cache de shaders da Intel", [local_low / "Intel" / "ShaderCache"]),
    ]


def _eh_link(entrada: os.DirEntry[str]) -> bool:
    # Junctions e links simbólicos podem apontar para fora da pasta: nunca seguimos.
    return entrada.is_symlink() or (hasattr(entrada, "is_junction") and entrada.is_junction())


def _percorrer(pasta: Path, idade_minima_s: int, apagar: bool, agora: float,
               med: Medicao, res: ResultadoLimpeza) -> None:
    try:
        entradas = list(os.scandir(pasta))
    except OSError:
        return
    for entrada in entradas:
        try:
            if _eh_link(entrada):
                continue
            if entrada.is_dir(follow_symlinks=False):
                _percorrer(Path(entrada.path), idade_minima_s, apagar, agora, med, res)
                if apagar:
                    try:
                        os.rmdir(entrada.path)  # só remove se ficou vazia
                    except OSError:
                        pass
                continue
            info = entrada.stat(follow_symlinks=False)
            if idade_minima_s and agora - info.st_mtime < idade_minima_s:
                continue
            med.bytes += info.st_size
            med.arquivos += 1
            if apagar:
                try:
                    os.remove(entrada.path)
                except PermissionError:
                    try:  # arquivos somente leitura
                        os.chmod(entrada.path, stat.S_IWRITE)
                        os.remove(entrada.path)
                    except OSError:
                        res.em_uso += 1
                        continue
                except OSError:
                    res.em_uso += 1
                    continue
                res.liberado += info.st_size
                res.apagados += 1
        except OSError:
            continue


def medir(alvo: AlvoLimpeza) -> Medicao:
    med, agora = Medicao(), time.time()
    for pasta in alvo.existentes:
        _percorrer(pasta, alvo.idade_minima_s, False, agora, med, ResultadoLimpeza())
    return med


def limpar(alvo: AlvoLimpeza) -> ResultadoLimpeza:
    res, agora = ResultadoLimpeza(), time.time()
    for pasta in alvo.existentes:
        log.debug("Limpando %s", pasta)
        _percorrer(pasta, alvo.idade_minima_s, True, agora, Medicao(), res)
    return res


class Limpeza(Ajuste):
    id = "limpeza"
    titulo = "Limpeza de temporários e cache de shaders"
    explicacao = (
        "Apaga arquivos temporários (com mais de 24h) e os caches de shaders das placas de vídeo. "
        "Limpar o cache de shaders é útil depois de atualizar o driver ou quando um jogo apresenta "
        "falhas gráficas, mas não aumenta o FPS: os jogos recompilam os shaders e as primeiras partidas "
        "podem ter alguns engasgos. Arquivos em uso são ignorados."
    )
    tecnico = "Exclui arquivos das pastas marcadas; não segue atalhos de pasta (junctions/symlinks)"
    texto_botao = "Limpar selecionados"
    repetivel = True
    reversivel = False  # arquivos temporários não têm "desfazer" (e não são necessários)

    def __init__(self, estado, alvos: list[AlvoLimpeza] | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(estado)
        self.alvos = alvos if alvos is not None else alvos_padrao()

    def status(self) -> StatusAjuste:
        opcoes, total = [], 0
        for alvo in self.alvos:
            if not alvo.existentes:
                continue
            med = medir(alvo)
            total += med.bytes
            opcoes.append(Opcao(alvo.id, alvo.nome, f"{tamanho(med.bytes)} · {med.arquivos} arquivos",
                                marcada=med.bytes > 0))
        if not opcoes:
            return StatusAjuste("Nada para limpar", "ok", aplicado=True, disponivel=False)
        return StatusAjuste(f"Até {tamanho(total)} podem ser liberados", "info" if total else "ok",
                            opcoes=opcoes)

    def _aplicar(self, opcoes: set[str] | None) -> Resultado:
        selecionados = [a for a in self.alvos if opcoes is None or a.id in opcoes]
        if not selecionados:
            return Resultado(False, "Nenhuma pasta selecionada.")
        total = ResultadoLimpeza()
        for alvo in selecionados:
            res = limpar(alvo)
            log.info("  %s: %s liberados (%d arquivos; %d em uso ignorados)",
                     alvo.nome, tamanho(res.liberado), res.apagados, res.em_uso)
            total.liberado += res.liberado
            total.apagados += res.apagados
            total.em_uso += res.em_uso
        msg = f"Limpeza concluída: {tamanho(total.liberado)} liberados ({total.apagados} arquivos)."
        if total.em_uso:
            msg += f" {total.em_uso} arquivos estavam em uso e foram mantidos."
        return Resultado(True, msg)
