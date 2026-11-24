"""Contrato comum de todos os ajustes: status, aplicar e desfazer."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..core.estado import Estado

log = logging.getLogger("otimizador.ajustes")


@dataclass
class Opcao:
    """Item que o usuário pode marcar ou desmarcar antes de aplicar (ex.: pastas da limpeza)."""
    id: str
    rotulo: str
    detalhe: str = ""
    marcada: bool = True


@dataclass
class StatusAjuste:
    texto: str
    nivel: str = "neutro"  # "ok" | "info" | "aviso" | "neutro"
    aplicado: bool = False  # já está no estado recomendado
    disponivel: bool = True  # False desativa o botão (ex.: não há SSD)
    opcoes: list[Opcao] = field(default_factory=list)


@dataclass
class Resultado:
    sucesso: bool
    mensagem: str
    requer_reinicio: bool = False


class Ajuste(ABC):
    id: str = ""
    titulo: str = ""
    explicacao: str = ""
    tecnico: str = ""  # o que é executado, para total transparência
    texto_botao: str = "Aplicar"
    altera_sistema: bool = True  # exige ponto de restauração antes
    reversivel: bool = True

    def __init__(self, estado: Estado) -> None:
        self.estado = estado

    # ------------------------------------------------------------ para as subclasses
    @abstractmethod
    def status(self) -> StatusAjuste: ...

    @abstractmethod
    def _aplicar(self, opcoes: set[str] | None) -> Resultado: ...

    def _desfazer(self, original: object) -> Resultado:
        raise NotImplementedError

    # ------------------------------------------------------------ usados pela interface
    def pode_desfazer(self) -> bool:
        return self.reversivel and self.estado.tem(self.id)

    def aplicar(self, opcoes: set[str] | None = None) -> Resultado:
        log.info("▶ Aplicando: %s", self.titulo)
        try:
            resultado = self._aplicar(opcoes)
        except Exception as erro:  # noqa: BLE001 - o erro vira mensagem para o usuário
            log.exception("Erro ao aplicar '%s'", self.titulo)
            resultado = Resultado(False, f"Erro inesperado: {erro}")
        self._registrar(resultado)
        return resultado

    def desfazer(self) -> Resultado:
        if not self.pode_desfazer():
            return Resultado(False, "Não há alteração deste app para desfazer.")
        log.info("↩ Desfazendo: %s", self.titulo)
        try:
            resultado = self._desfazer(self.estado.original(self.id))
            if resultado.sucesso:
                self.estado.descartar(self.id)
        except Exception as erro:  # noqa: BLE001
            log.exception("Erro ao desfazer '%s'", self.titulo)
            resultado = Resultado(False, f"Erro inesperado: {erro}")
        self._registrar(resultado)
        return resultado

    @staticmethod
    def _registrar(resultado: Resultado) -> None:
        if resultado.sucesso:
            log.info("✔ %s", resultado.mensagem)
        else:
            log.error("✖ %s", resultado.mensagem)
        if resultado.requer_reinicio:
            log.info("  Reinicie o computador para a alteração ter efeito.")
