import pytest

from otimizador.core.d3dkmt import CapacidadeHags, interpretar_bits
from otimizador.diagnostico.sistema import (GUID_ALTO_DESEMPENHO, analisar_hags,
                                            analisar_inicializacao, analisar_modo_jogo,
                                            analisar_planos, analisar_trim, executavel_do_comando,
                                            plano_ativo)

from .conftest import FSUTIL_TRIM_LIGADO, POWERCFG_PT

POWERCFG_EN = """\
Existing Power Schemes (* Active)
-----------------------------------
Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
Power Scheme GUID: 0d1f3a2b-1111-2222-3333-444455556666  (High performance) *
"""


def test_planos_em_portugues():
    planos = analisar_planos(POWERCFG_PT)
    assert len(planos) == 3
    ativo = plano_ativo(planos)
    assert ativo.nome == "Equilibrado" and not ativo.eh_alto_desempenho
    assert any(p.guid == GUID_ALTO_DESEMPENHO for p in planos)


def test_plano_duplicado_em_ingles_e_reconhecido_pelo_nome():
    ativo = plano_ativo(analisar_planos(POWERCFG_EN))
    assert ativo.eh_alto_desempenho


@pytest.mark.parametrize("saida, esperado", [
    (FSUTIL_TRIM_LIGADO, True),
    ("NTFS DisableDeleteNotify = 1  (Disabled)", False),
    ("", None),
])
def test_trim(saida, esperado):
    assert analisar_trim(saida) is esperado


def test_modo_jogo_sem_registro_e_ligado_por_padrao():
    modo = analisar_modo_jogo(None)
    assert modo.ativado and "padrão" in modo.descricao
    assert not analisar_modo_jogo(0).ativado


def test_bits_hags():
    assert interpretar_bits(0b1011) == CapacidadeHags(suportado=True, ativado=True, ativado_por_padrao=False)


def test_hags_pendente_de_reinicio():
    hags = analisar_hags(CapacidadeHags(True, False, False), 2)
    assert hags.pendente_reinicio
    assert "reiniciar" in hags.descricao


def test_hags_nao_suportado():
    hags = analisar_hags(CapacidadeHags(False, False, False), None)
    assert hags.suportado is False and hags.ativado is False


@pytest.mark.parametrize("comando, exe", [
    ('"C:\\Program Files\\App\\app.exe" --silent', "app.exe"),
    ("D:\\Riot Games\\Riot Client\\RiotClientServices.exe --launch", "RiotClientServices.exe"),
    ("%windir%\\system32\\SecurityHealthSystray.exe", "SecurityHealthSystray.exe"),
    ("Atalho.lnk", "Atalho.lnk"),
])
def test_executavel_do_comando(comando, exe):
    assert executavel_do_comando(comando) == exe


def test_inicializacao_status_aprovado(cim_real):
    aprovados = {"HKCU\\Run": {"Discord": bytes([3]) + bytes(11)}, "HKLM\\Run": {"SecurityHealth": bytes([4]) + bytes(11)}}
    programas = {p.nome: p for p in analisar_inicializacao(cim_real["inicializacao"], aprovados)}
    assert programas["Discord"].ativo is False  # desativado no Gerenciador de Tarefas
    assert programas["Steam"].ativo is True  # sem registro em StartupApproved = ativo
    assert programas["SecurityHealth"].ativo is True
    assert programas["Steam"].escopo == "Usuário atual"
    assert programas["Riot Vanguard"].escopo == "Todos os usuários"
    # Nunca expõe o caminho completo (pode conter o nome do usuário)
    assert programas["Discord"].executavel == "Discord.exe"


def test_inicializacao_desativados_ficam_no_fim(cim_real):
    aprovados = {"HKCU\\Run": {"Discord": bytes([3])}}
    programas = analisar_inicializacao(cim_real["inicializacao"], aprovados)
    assert programas[-1].nome == "Discord"
