"""Ajustes seguros e reversíveis. Nenhum é aplicado automaticamente."""

from __future__ import annotations

from ..core.estado import Estado
from .agendamento_gpu import AgendamentoGpu
from .base import Ajuste, Opcao, Resultado, StatusAjuste
from .energia import PlanoAltoDesempenho
from .inicializacao import AbrirInicializacao
from .limpeza import Limpeza
from .modo_jogo import ModoDeJogo
from .trim import TrimSsd

__all__ = ["Ajuste", "Opcao", "Resultado", "StatusAjuste", "criar_ajustes"]


def criar_ajustes(estado: Estado) -> list[Ajuste]:
    return [
        PlanoAltoDesempenho(estado),
        TrimSsd(estado),
        ModoDeJogo(estado),
        AgendamentoGpu(estado),
        Limpeza(estado),
        AbrirInicializacao(estado),
    ]
