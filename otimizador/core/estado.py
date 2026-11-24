"""Guarda o valor original de cada configuração alterada, para permitir desfazer."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .log import pasta_dados

log = logging.getLogger("otimizador.estado")


class Estado:
    def __init__(self, arquivo: Path | None = None) -> None:
        self.arquivo = arquivo or pasta_dados() / "estado.json"
        self._trava = threading.Lock()
        self._dados: dict[str, dict[str, Any]] = self._carregar()

    def _carregar(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(self.arquivo.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as erro:
            log.warning("Não foi possível ler %s (%s). Começando do zero.", self.arquivo, erro)
            return {}

    def _salvar(self) -> None:
        self.arquivo.write_text(json.dumps(self._dados, indent=2, ensure_ascii=False), encoding="utf-8")

    def guardar_original(self, chave: str, valor: Any) -> None:
        """Salva o valor anterior apenas na primeira alteração.

        Aplicar o mesmo ajuste duas vezes não pode sobrescrever o valor original,
        senão o "Desfazer" voltaria para o estado já modificado.
        """
        with self._trava:
            if chave in self._dados:
                return
            self._dados[chave] = {"valor": valor, "data": datetime.now().isoformat(timespec="seconds")}
            self._salvar()

    def tem(self, chave: str) -> bool:
        return chave in self._dados

    def original(self, chave: str) -> Any:
        return self._dados[chave]["valor"]

    def descartar(self, chave: str) -> None:
        with self._trava:
            if self._dados.pop(chave, None) is not None:
                self._salvar()
