"""Consulta ao driver de vídeo (API D3DKMT do Windows) sobre o agendamento de GPU.

O registro (HwSchMode) só mostra a preferência salva; quando a chave não existe,
o Windows decide sozinho. Perguntar ao driver dá o estado real e se a GPU suporta.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

KMTQAITYPE_WDDM_2_7_CAPS = 70


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _ADAPTERINFO(ctypes.Structure):
    _fields_ = [
        ("hAdapter", wintypes.UINT),
        ("AdapterLuid", _LUID),
        ("NumOfSources", wintypes.ULONG),
        ("bPrecisePresentRegionsPreferred", wintypes.BOOL),
    ]


class _ENUMADAPTERS2(ctypes.Structure):
    _fields_ = [("NumAdapters", wintypes.ULONG), ("pAdapters", ctypes.POINTER(_ADAPTERINFO))]


class _QUERYADAPTERINFO(ctypes.Structure):
    _fields_ = [
        ("hAdapter", wintypes.UINT),
        ("Type", ctypes.c_int),
        ("pPrivateDriverData", ctypes.c_void_p),
        ("PrivateDriverDataSize", wintypes.UINT),
    ]


class _CLOSEADAPTER(ctypes.Structure):
    _fields_ = [("hAdapter", wintypes.UINT)]


@dataclass
class CapacidadeHags:
    suportado: bool
    ativado: bool
    ativado_por_padrao: bool


def interpretar_bits(valor: int) -> CapacidadeHags:
    """D3DKMT_WDDM_2_7_CAPS: bit 0 = suportado, bit 1 = ativado, bit 2 = ativado por padrão."""
    return CapacidadeHags(bool(valor & 1), bool(valor & 2), bool(valor & 4))


def consultar_hags() -> CapacidadeHags | None:
    """Estado do agendamento de GPU na placa que suporta o recurso (ou None se nenhuma)."""
    try:
        gdi = ctypes.WinDLL("gdi32")
    except OSError:
        return None

    enum = _ENUMADAPTERS2(0, None)
    if gdi.D3DKMTEnumAdapters2(ctypes.byref(enum)) != 0 or enum.NumAdapters == 0:
        return None
    adaptadores = (_ADAPTERINFO * enum.NumAdapters)()
    enum.pAdapters = adaptadores
    if gdi.D3DKMTEnumAdapters2(ctypes.byref(enum)) != 0:
        return None

    encontrados: list[CapacidadeHags] = []
    for adaptador in adaptadores[: enum.NumAdapters]:
        caps = wintypes.UINT(0)
        consulta = _QUERYADAPTERINFO(
            adaptador.hAdapter, KMTQAITYPE_WDDM_2_7_CAPS,
            ctypes.cast(ctypes.byref(caps), ctypes.c_void_p), ctypes.sizeof(caps),
        )
        if gdi.D3DKMTQueryAdapterInfo(ctypes.byref(consulta)) == 0:
            encontrados.append(interpretar_bits(caps.value))
        gdi.D3DKMTCloseAdapter(ctypes.byref(_CLOSEADAPTER(adaptador.hAdapter)))

    suportados = [c for c in encontrados if c.suportado]
    return suportados[0] if suportados else (encontrados[0] if encontrados else None)
