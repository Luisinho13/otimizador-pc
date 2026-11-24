"""Formatação de números no padrão brasileiro."""

from __future__ import annotations


def tamanho(bytes_: float | int | None) -> str:
    """1536 -> '1,5 KB'. Usa base 1024, igual ao Explorador de Arquivos."""
    if bytes_ is None:
        return "—"
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if abs(valor) < 1024 or unidade == "TB":
            casas = 0 if unidade == "B" else 1
            return f"{valor:,.{casas}f} {unidade}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor /= 1024
    return f"{valor} TB"  # inalcançável


def gb(bytes_: float | int) -> float:
    return float(bytes_) / 1024**3


def porcentagem(parte: float, total: float) -> str:
    if not total:
        return "—"
    return f"{parte / total * 100:.0f}%"
