"""Interpretação das configurações do Windows: energia, TRIM, Modo de Jogo, HAGS e inicialização."""

from __future__ import annotations

import ntpath
import re
from dataclasses import dataclass
from typing import Any

from ..core.d3dkmt import CapacidadeHags
from ..core.shell import como_lista

# --------------------------------------------------------------------------- Energia

GUID_EQUILIBRADO = "381b4222-f694-41f0-9685-ff5bb260df2e"
GUID_ALTO_DESEMPENHO = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_ECONOMIA = "a1841308-3541-4fab-bc81-f71556f20b4a"
GUID_DESEMPENHO_MAXIMO = "e9a42b02-d5df-448d-aa00-03f14749eb61"

NOMES_ALTO_DESEMPENHO = ("alto desempenho", "high performance")

_RE_PLANO = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*\((.*?)\)\s*(\*)?\s*$",
    flags=re.I | re.M,
)


@dataclass
class PlanoEnergia:
    guid: str
    nome: str
    ativo: bool

    @property
    def eh_alto_desempenho(self) -> bool:
        return (self.guid in (GUID_ALTO_DESEMPENHO, GUID_DESEMPENHO_MAXIMO)
                or any(n in self.nome.lower() for n in NOMES_ALTO_DESEMPENHO))


def analisar_planos(saida_powercfg: str) -> list[PlanoEnergia]:
    """Lê 'powercfg /list'. Usa o GUID (não o nome), que não muda com o idioma."""
    return [PlanoEnergia(m.group(1).lower(), m.group(2).strip(), bool(m.group(3)))
            for m in _RE_PLANO.finditer(saida_powercfg)]


def plano_ativo(planos: list[PlanoEnergia]) -> PlanoEnergia | None:
    return next((p for p in planos if p.ativo), None)


# --------------------------------------------------------------------------- TRIM


def analisar_trim(saida_fsutil: str) -> bool | None:
    """'NTFS DisableDeleteNotify = 0' significa TRIM ATIVADO (a lógica é invertida)."""
    achado = re.search(r"NTFS\s+DisableDeleteNotify\s*=\s*(\d)", saida_fsutil, flags=re.I)
    if not achado:
        return None
    return achado.group(1) == "0"


# --------------------------------------------------------------------------- Modo de Jogo


@dataclass
class ModoJogo:
    ativado: bool
    valor_registro: int | None

    @property
    def descricao(self) -> str:
        estado = "Ativado" if self.ativado else "Desativado"
        return f"{estado} (padrão do Windows)" if self.valor_registro is None else estado


def analisar_modo_jogo(valor: int | None) -> ModoJogo:
    # Sem o valor no registro, o Windows 10/11 deixa o Modo de Jogo ligado.
    return ModoJogo(ativado=valor != 0, valor_registro=valor)


# --------------------------------------------------------------------------- HAGS


@dataclass
class AgendamentoGpu:
    suportado: bool | None  # None = não foi possível consultar o driver
    ativado: bool | None
    valor_registro: int | None  # 2 = ligado, 1 = desligado, None = padrão

    @property
    def pendente_reinicio(self) -> bool:
        """O registro pede um estado diferente do que o driver está usando agora."""
        if self.ativado is None or self.valor_registro not in (1, 2):
            return False
        return (self.valor_registro == 2) != self.ativado

    @property
    def descricao(self) -> str:
        if self.suportado is False:
            return "Não suportado por esta placa/driver"
        if self.ativado is None:
            if self.valor_registro == 2:
                return "Ativado (pelo registro)"
            if self.valor_registro == 1:
                return "Desativado (pelo registro)"
            return "Desconhecido"
        texto = "Ativado" if self.ativado else "Desativado"
        if self.pendente_reinicio:
            texto += " — muda após reiniciar"
        return texto


def analisar_hags(caps: CapacidadeHags | None, valor_registro: int | None) -> AgendamentoGpu:
    if caps is None:
        return AgendamentoGpu(None, None, valor_registro)
    return AgendamentoGpu(caps.suportado, caps.ativado if caps.suportado else False, valor_registro)


# --------------------------------------------------------------------------- Inicialização


@dataclass
class ProgramaInicializacao:
    nome: str
    executavel: str
    escopo: str  # "Usuário atual" | "Todos os usuários"
    origem: str  # "Registro" | "Pasta Inicializar"
    ativo: bool | None


def executavel_do_comando(comando: str) -> str:
    """Devolve só o nome do programa (sem caminho, para não expor pastas do usuário)."""
    comando = comando.strip()
    if comando.startswith('"'):
        caminho = comando[1:].split('"', 1)[0]
    else:
        achado = re.match(r"(.+?\.(exe|lnk|bat|cmd|com|url))(\s|$)", comando, flags=re.I)
        caminho = achado.group(1) if achado else comando.split(" ", 1)[0]
    return ntpath.basename(caminho) or caminho


def _classificar_local(local: str) -> tuple[str, str, str | None]:
    """(escopo, origem, chave em StartupApproved) a partir do campo Location do WMI."""
    alto = local.upper()
    if alto == "STARTUP":
        return "Usuário atual", "Pasta Inicializar", "HKCU\\StartupFolder"
    if alto == "COMMON STARTUP":
        return "Todos os usuários", "Pasta Inicializar", "HKLM\\StartupFolder"
    usuario = alto.startswith(("HKU\\", "HKCU\\"))
    escopo = "Usuário atual" if usuario else "Todos os usuários"
    if not alto.endswith("\\RUN"):
        return escopo, "Registro", None  # RunOnce etc.: o Gerenciador de Tarefas não controla
    if usuario:
        return escopo, "Registro", "HKCU\\Run"
    return escopo, "Registro", "HKLM\\Run32" if "WOW6432NODE" in alto else "HKLM\\Run"


def analisar_inicializacao(dados: Any, aprovados: dict[str, dict[str, bytes]]) -> list[ProgramaInicializacao]:
    programas = []
    for item in como_lista(dados):
        nome = str(item.get("Name") or "").strip()
        comando = str(item.get("Command") or "")
        escopo, origem, chave = _classificar_local(str(item.get("Location") or ""))

        ativo: bool | None = None
        if chave:
            # Na pasta Inicializar, o nome guardado é o do arquivo (ex.: "App.lnk").
            nome_aprovado = comando if origem == "Pasta Inicializar" else nome
            dados_aprovado = aprovados.get(chave, {}).get(nome_aprovado)
            # Primeiro byte par = ativado, ímpar = desativado. Sem registro = ativado.
            ativo = True if not dados_aprovado else (dados_aprovado[0] & 1) == 0

        programas.append(ProgramaInicializacao(nome, executavel_do_comando(comando), escopo, origem, ativo))
    return sorted(programas, key=lambda p: (p.ativo is False, p.nome.lower()))
