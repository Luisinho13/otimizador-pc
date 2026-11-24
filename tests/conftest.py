import json
from pathlib import Path

import pytest

DADOS = Path(__file__).parent / "dados"

POWERCFG_PT = """\
Esquemas de Energia Existentes (* Ativos)
-----------------------------------
GUID do Esquema de Energia: 381b4222-f694-41f0-9685-ff5bb260df2e  (Equilibrado) *
GUID do Esquema de Energia: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (Alto desempenho)
GUID do Esquema de Energia: a1841308-3541-4fab-bc81-f71556f20b4a  (Economia de energia)
"""

FSUTIL_TRIM_LIGADO = (
    "NTFS DisableDeleteNotify = 0  (Permite que operações TRIM sejam enviadas ao dispositivo)\r\n"
    "ReFS DisableDeleteNotify = 0  (Permite que operações TRIM sejam enviadas ao dispositivo)\r\n"
)


@pytest.fixture
def cim_real() -> dict:
    """Saída real da coleta em um i5-9400F + RTX 5060 (dados pessoais removidos)."""
    return json.loads((DADOS / "cim_i5_9400f.json").read_text(encoding="utf-8"))
