import copy
from datetime import date

from otimizador.core.d3dkmt import CapacidadeHags
from otimizador.diagnostico import montar_diagnostico

from .conftest import FSUTIL_TRIM_LIGADO, POWERCFG_PT

HOJE = date(2026, 11, 24)


def _brutos(cim):
    return {
        "cim": cim,
        "nvidia_smi": [],
        "planos": POWERCFG_PT,
        "trim": FSUTIL_TRIM_LIGADO,
        "modo_jogo": None,
        "hags": (CapacidadeHags(True, True, False), None),
        "aprovados": {},
    }


def _titulos(diag):
    return [a.titulo for a in diag.achados]


def test_diagnostico_completo(cim_real):
    diag = montar_diagnostico(_brutos(cim_real), hoje=HOJE)
    assert diag.placa_mae == "ASUSTeK COMPUTER INC. TUF H310M-PLUS GAMING/BR"
    assert diag.tem_ssd
    assert diag.plano_ativo.nome == "Equilibrado"
    titulos = _titulos(diag)
    assert "Memória abaixo da velocidade anunciada" in titulos
    assert "Pentes de modelos diferentes" in titulos
    assert "Plano de energia: Equilibrado" in titulos
    assert not any("espaço" in t for t in titulos)


def test_pouco_espaco_e_trim_desligado(cim_real):
    cim = copy.deepcopy(cim_real)
    for vol in cim["volumes"]:
        if vol["DriveLetter"] == "C":
            vol["SizeRemaining"] = vol["Size"] * 0.05
    brutos = _brutos(cim) | {"trim": "NTFS DisableDeleteNotify = 1"}
    titulos = _titulos(montar_diagnostico(brutos, hoje=HOJE))
    assert "Pouco espaço livre em C:" in titulos
    assert "TRIM desativado" in titulos


def test_driver_antigo(cim_real):
    cim = copy.deepcopy(cim_real)
    cim["gpu"]["DriverDate"] = "2025-01-10"
    titulos = _titulos(montar_diagnostico(_brutos(cim), hoje=HOJE))
    assert any(t.startswith("Driver de vídeo com") for t in titulos)


def test_dados_vazios_nao_quebram():
    diag = montar_diagnostico({}, erros=["cim: falhou"], hoje=HOJE)
    assert diag.processadores == [] and diag.discos == []
    assert diag.memoria.canal == "Não detectado"
    assert diag.achados[0].nivel == "ok"
