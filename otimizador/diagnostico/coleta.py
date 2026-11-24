"""Coleta dos dados brutos do sistema (somente leitura).

Tudo que vem do WMI/CIM é buscado em um único processo do PowerShell, porque
abrir o PowerShell é a parte mais lenta. Cada consulta é isolada em um try,
para que a falha de uma não impeça as outras.
"""

from __future__ import annotations

import logging
import shutil
import winreg
from typing import Any

from ..core import registro
from ..core.d3dkmt import CapacidadeHags, consultar_hags
from ..core.shell import executar, powershell_json

log = logging.getLogger("otimizador.diagnostico")

SCRIPT_CIM = r"""
function T([scriptblock]$b) { try { & $b } catch { $null } }
$classeVideo = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*'
[pscustomobject]@{
  so = T { Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber }
  placa_mae = T { Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product }
  cpu = T { @(Get-CimInstance Win32_Processor |
      Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed) }
  gpu = T { @(Get-CimInstance Win32_VideoController |
      Select-Object Name, DriverVersion, PNPDeviceID,
        @{n='DriverDate'; e={ if ($_.DriverDate) { $_.DriverDate.ToString('yyyy-MM-dd') } }}) }
  gpu_vram = T { @(Get-ItemProperty $classeVideo -ErrorAction SilentlyContinue |
      Select-Object DriverDesc, @{n='Vram'; e={ $_.'HardwareInformation.qwMemorySize' }}) }
  ram = T { @(Get-CimInstance Win32_PhysicalMemory |
      Select-Object Capacity, Speed, ConfiguredClockSpeed, DeviceLocator, BankLabel, Manufacturer, PartNumber) }
  ram_slots = T { (Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object MemoryDevices -Sum).Sum }
  discos = T { @(Get-PhysicalDisk | Select-Object DeviceId, FriendlyName,
      @{n='MediaType'; e={ [string]$_.MediaType }}, @{n='BusType'; e={ [string]$_.BusType }}, Size) }
  particoes = T { @(Get-Partition | Where-Object DriveLetter |
      Select-Object DiskNumber, @{n='DriveLetter'; e={ [string]$_.DriveLetter }}) }
  volumes = T { @(Get-Volume | Where-Object DriveLetter |
      Select-Object @{n='DriveLetter'; e={ [string]$_.DriveLetter }}, FileSystemLabel, FileSystem,
        Size, SizeRemaining, @{n='DriveType'; e={ [string]$_.DriveType }}) }
  inicializacao = T { @(Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location) }
}
"""

CHAVE_GAMEBAR = r"Software\Microsoft\GameBar"
CHAVE_GRAPHICS = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
CHAVE_APROVADOS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def coletar_cim() -> dict[str, Any]:
    return powershell_json(SCRIPT_CIM, timeout=120) or {}


def coletar_nvidia_smi() -> list[dict[str, str]]:
    """Dados extras das placas NVIDIA (versão do driver no formato do site da NVIDIA)."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    saida = executar([exe, "--query-gpu=name,driver_version,memory.total",
                      "--format=csv,noheader,nounits"], timeout=20)
    if not saida.ok:
        return []
    placas = []
    for linha in saida.stdout.strip().splitlines():
        partes = [p.strip() for p in linha.split(",")]
        if len(partes) == 3:
            placas.append({"nome": partes[0], "driver": partes[1], "vram_mib": partes[2]})
    return placas


def coletar_planos() -> str:
    """Saída de 'powercfg /list' (funciona sem privilégios, ao contrário do WMI)."""
    saida = executar(["powercfg", "/list"], timeout=20)
    return saida.stdout if saida.ok else ""


def coletar_trim() -> str:
    saida = executar(["fsutil", "behavior", "query", "DisableDeleteNotify"], timeout=20)
    return saida.stdout if saida.ok else ""


def coletar_modo_jogo() -> int | None:
    return registro.ler_dword(winreg.HKEY_CURRENT_USER, CHAVE_GAMEBAR, "AutoGameModeEnabled")


def coletar_hags() -> tuple[CapacidadeHags | None, int | None]:
    return consultar_hags(), registro.ler_dword(winreg.HKEY_LOCAL_MACHINE, CHAVE_GRAPHICS, "HwSchMode")


def coletar_inicializacao_aprovada() -> dict[str, dict[str, bytes]]:
    """Itens ativados/desativados pelo Gerenciador de Tarefas (StartupApproved)."""
    fontes = {
        "HKCU\\Run": (winreg.HKEY_CURRENT_USER, "Run"),
        "HKLM\\Run": (winreg.HKEY_LOCAL_MACHINE, "Run"),
        "HKLM\\Run32": (winreg.HKEY_LOCAL_MACHINE, "Run32"),
        "HKCU\\StartupFolder": (winreg.HKEY_CURRENT_USER, "StartupFolder"),
        "HKLM\\StartupFolder": (winreg.HKEY_LOCAL_MACHINE, "StartupFolder"),
    }
    resultado: dict[str, dict[str, bytes]] = {}
    for nome, (raiz, sub) in fontes.items():
        valores: dict[str, bytes] = {}
        try:
            with winreg.OpenKey(raiz, f"{CHAVE_APROVADOS}\\{sub}") as chave:
                i = 0
                while True:
                    try:
                        valor_nome, dados, _ = winreg.EnumValue(chave, i)
                    except OSError:
                        break
                    if isinstance(dados, bytes):
                        valores[valor_nome] = dados
                    i += 1
        except OSError:
            pass
        resultado[nome] = valores
    return resultado
