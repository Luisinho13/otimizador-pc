"""Plano de energia Alto desempenho."""

from __future__ import annotations

import re

from ..core.shell import executar
from ..diagnostico.coleta import coletar_planos
from ..diagnostico.sistema import (GUID_ALTO_DESEMPENHO, GUID_EQUILIBRADO, analisar_planos,
                                   plano_ativo)
from .base import Ajuste, Resultado, StatusAjuste


class PlanoAltoDesempenho(Ajuste):
    id = "plano_energia"
    titulo = "Plano de energia: Alto desempenho"
    explicacao = (
        "Impede o processador de reduzir o clock e de \"estacionar\" núcleos para economizar energia. "
        "Em jogos o ganho costuma ser pequeno (menos engasgos em alguns casos) e o consumo em repouso "
        "aumenta um pouco. Em processadores Ryzen recentes o plano Equilibrado já é bem eficiente, "
        "então vale testar e comparar."
    )
    tecnico = f"powercfg /setactive {GUID_ALTO_DESEMPENHO} (o plano anterior é guardado para desfazer)"

    def status(self) -> StatusAjuste:
        ativo = plano_ativo(analisar_planos(coletar_planos()))
        if ativo is None:
            return StatusAjuste("Não foi possível ler o plano ativo", "aviso")
        if ativo.eh_alto_desempenho:
            return StatusAjuste(f"Ativo: {ativo.nome}", "ok", aplicado=True)
        return StatusAjuste(f"Ativo: {ativo.nome}", "info")

    def _aplicar(self, opcoes: set[str] | None) -> Resultado:
        planos = analisar_planos(coletar_planos())
        ativo = plano_ativo(planos)
        if ativo and ativo.eh_alto_desempenho:
            return Resultado(True, f"O plano \"{ativo.nome}\" já está ativo.")

        alvo = next((p for p in planos if p.guid == GUID_ALTO_DESEMPENHO), None) \
            or next((p for p in planos if p.eh_alto_desempenho), None)
        if alvo:
            guid = alvo.guid
        else:
            # Algumas instalações escondem o plano; ele pode ser recriado a partir do modelo.
            saida = executar(["powercfg", "-duplicatescheme", GUID_ALTO_DESEMPENHO])
            achado = re.search(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", saida.stdout, re.I)
            if not saida.ok or not achado:
                return Resultado(False, "Este PC não oferece o plano Alto desempenho "
                                        f"(comum em notebooks com Modern Standby). {saida.erro()}")
            guid = achado.group(0).lower()

        if ativo:
            self.estado.guardar_original(self.id, ativo.guid)
        saida = executar(["powercfg", "/setactive", guid])
        if not saida.ok:
            return Resultado(False, f"Falha ao ativar o plano: {saida.erro()}")
        return Resultado(True, "Plano Alto desempenho ativado.")

    def _desfazer(self, original: object) -> Resultado:
        saida = executar(["powercfg", "/setactive", str(original)])
        if saida.ok:
            return Resultado(True, "Plano de energia anterior restaurado.")
        # O plano anterior pode ter sido apagado; volta para o Equilibrado.
        saida = executar(["powercfg", "/setactive", GUID_EQUILIBRADO])
        if saida.ok:
            return Resultado(True, "O plano anterior não existe mais; o plano Equilibrado foi ativado.")
        return Resultado(False, f"Falha ao restaurar o plano: {saida.erro()}")
