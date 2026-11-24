"""Interpretação dos dados de hardware: CPU, GPU, memória e discos.

Funções puras (recebem os dados brutos da coleta), para facilitar os testes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..core.shell import como_lista

# --------------------------------------------------------------------------- CPU


@dataclass
class Processador:
    nome: str
    nucleos: int
    threads: int
    clock_base_mhz: int


def analisar_cpu(dados: Any) -> list[Processador]:
    return [
        Processador(
            nome=" ".join(str(c.get("Name") or "Desconhecido").split()),
            nucleos=int(c.get("NumberOfCores") or 0),
            threads=int(c.get("NumberOfLogicalProcessors") or 0),
            clock_base_mhz=int(c.get("MaxClockSpeed") or 0),
        )
        for c in como_lista(dados)
    ]


# --------------------------------------------------------------------------- GPU

ADAPTADORES_VIRTUAIS = ("microsoft basic", "microsoft remote", "parsec", "virtual display", "meta virtual")


@dataclass
class PlacaVideo:
    nome: str
    driver: str
    data_driver: str | None
    vram_bytes: int | None
    fabricante: str


def versao_driver_nvidia(versao_windows: str) -> str | None:
    """'32.0.16.2140' (formato do Windows) -> '621.40' (formato do site da NVIDIA)."""
    partes = versao_windows.split(".")
    if len(partes) != 4:
        return None
    digitos = (partes[2] + partes[3])[-5:]
    if len(digitos) != 5 or not digitos.isdigit():
        return None
    return f"{digitos[:3]}.{digitos[3:]}"


def _fabricante(pnp: str, nome: str) -> str:
    pnp, nome = pnp.upper(), nome.upper()
    if "VEN_10DE" in pnp or "NVIDIA" in nome:
        return "NVIDIA"
    if "VEN_1002" in pnp or "AMD" in nome or "RADEON" in nome:
        return "AMD"
    if "VEN_8086" in pnp or "INTEL" in nome:
        return "Intel"
    return "Outro"


def analisar_gpu(dados: Any, vram_registro: Any, nvidia_smi: list[dict[str, str]]) -> list[PlacaVideo]:
    vram_por_nome = {}
    for item in como_lista(vram_registro):
        vram = item.get("Vram")
        if isinstance(vram, int) and vram > 0:
            vram_por_nome[str(item.get("DriverDesc", "")).strip()] = vram
    smi_por_nome = {p["nome"]: p for p in nvidia_smi}

    placas = []
    for g in como_lista(dados):
        nome = str(g.get("Name") or "Desconhecida").strip()
        if any(v in nome.lower() for v in ADAPTADORES_VIRTUAIS):
            continue
        fabricante = _fabricante(str(g.get("PNPDeviceID") or ""), nome)
        driver = str(g.get("DriverVersion") or "—")
        vram = vram_por_nome.get(nome)

        smi = smi_por_nome.get(nome)
        if smi:
            driver = smi["driver"]
            if smi.get("vram_mib", "").isdigit():
                vram = int(smi["vram_mib"]) * 1024**2
        elif fabricante == "NVIDIA":
            driver = versao_driver_nvidia(driver) or driver

        placas.append(PlacaVideo(nome, driver, g.get("DriverDate"), vram, fabricante))
    return placas


# --------------------------------------------------------------------------- Memória

VELOCIDADES_DDR = {
    1600, 1866, 2133, 2400, 2666, 2667, 2800, 2933, 3000, 3200, 3333, 3466, 3600, 3733, 3800,
    4000, 4133, 4266, 4400, 4600, 4800, 5200, 5600, 6000, 6200, 6400, 6600, 6800, 7200, 7600, 8000,
}
# Abreviações comuns em part numbers: Crucial BL8G26C16 -> 2666, Kingston KF432C16 -> 3200
VELOCIDADES_ABREVIADAS = {
    16: 1600, 18: 1866, 21: 2133, 24: 2400, 26: 2666, 28: 2800, 29: 2933, 30: 3000, 32: 3200,
    34: 3466, 36: 3600, 37: 3733, 38: 3800, 40: 4000, 41: 4133, 42: 4266, 44: 4400, 46: 4600,
    48: 4800, 52: 5200, 56: 5600, 60: 6000, 62: 6200, 64: 6400, 66: 6600, 68: 6800, 72: 7200,
    76: 7600, 80: 8000,
}


def velocidade_pelo_part_number(part_number: str) -> int | None:
    """Estima a velocidade anunciada (XMP/EXPO) pelo código do pente. Heurística!"""
    codigo = part_number.strip().upper()
    for numero in re.findall(r"(?<!\d)(\d{4})(?!\d)", codigo):
        if int(numero) in VELOCIDADES_DDR:
            return int(numero)
    abreviado = re.search(r"(\d{2})C\d{2}", codigo)  # velocidade seguida da latência (C15, C16...)
    if abreviado:
        return VELOCIDADES_ABREVIADAS.get(int(abreviado.group(1)))
    return None


def canal_do_pente(slot: str, banco: str) -> str | None:
    """Extrai o canal (A, B...) dos nomes de slot que a BIOS informa.

    Exemplos reais: ASUS 'ChannelA-DIMM1', AMD 'P0 CHANNEL A', MSI 'DIMMA1', 'DIMM_B2'.
    """
    for texto in (slot, banco):
        achado = re.search(r"CHANNEL\s*-?\s*([A-H])(?![A-Z])", texto, flags=re.I)
        if achado:
            return achado.group(1).upper()
    achado = re.search(r"DIMM[\s_-]?([A-H])\d", slot, flags=re.I)
    return achado.group(1).upper() if achado else None


@dataclass
class Pente:
    capacidade_bytes: int
    mhz_atual: int
    mhz_jedec: int
    mhz_anunciado: int | None
    slot: str
    canal: str | None
    fabricante: str
    modelo: str


@dataclass
class Memoria:
    pentes: list[Pente]
    slots_total: int | None
    total_bytes: int
    canal: str  # texto para a interface
    dual_channel: bool | None  # None = não foi possível ter certeza
    mhz_atual: int
    mhz_anunciado: int | None
    modelos_misturados: bool
    abaixo_do_anunciado: bool = field(init=False)

    def __post_init__(self) -> None:
        self.abaixo_do_anunciado = bool(self.mhz_anunciado and self.mhz_atual
                                        and self.mhz_atual < self.mhz_anunciado - 50)


def analisar_memoria(dados: Any, slots_total: Any) -> Memoria:
    pentes = []
    for p in como_lista(dados):
        slot = str(p.get("DeviceLocator") or "").strip()
        banco = str(p.get("BankLabel") or "").strip()
        modelo = str(p.get("PartNumber") or "").strip()
        jedec = int(p.get("Speed") or 0)
        pentes.append(Pente(
            capacidade_bytes=int(p.get("Capacity") or 0),
            mhz_atual=int(p.get("ConfiguredClockSpeed") or jedec),
            mhz_jedec=jedec,
            mhz_anunciado=velocidade_pelo_part_number(modelo),
            slot=slot or banco or "?",
            canal=canal_do_pente(slot, banco),
            fabricante=str(p.get("Manufacturer") or "").strip(),
            modelo=modelo,
        ))

    quantidade = len(pentes)
    canais = {p.canal for p in pentes if p.canal}
    if quantidade == 0:
        texto, dual = "Não detectado", None
    elif quantidade == 1:
        texto, dual = "Single channel (1 pente)", False
    elif len(canais) >= 2:
        texto, dual = f"Dual channel ({quantidade} pentes em {len(canais)} canais)", True
    elif len(canais) == 1 and all(p.canal for p in pentes):
        texto, dual = "Single channel (pentes no mesmo canal)", False
    elif quantidade % 2 == 0:
        texto, dual = f"Provavelmente dual channel ({quantidade} pentes)", None
    else:
        texto, dual = f"Indefinido ({quantidade} pentes)", None

    anunciados = [p.mhz_anunciado for p in pentes if p.mhz_anunciado]
    # Com pentes diferentes, todos rodam na velocidade do mais lento.
    mhz_anunciado = min(anunciados) if len(anunciados) == quantidade and anunciados else None
    if mhz_anunciado is None and pentes:
        mhz_anunciado = max(p.mhz_jedec for p in pentes) or None

    modelos = {(p.fabricante.upper(), p.modelo.upper()) for p in pentes}
    return Memoria(
        pentes=pentes,
        slots_total=int(slots_total) if slots_total else None,
        total_bytes=sum(p.capacidade_bytes for p in pentes),
        canal=texto,
        dual_channel=dual,
        mhz_atual=min((p.mhz_atual for p in pentes), default=0),
        mhz_anunciado=mhz_anunciado,
        modelos_misturados=len(modelos) > 1,
    )


# --------------------------------------------------------------------------- Discos


@dataclass
class Volume:
    letra: str
    rotulo: str
    sistema_arquivos: str
    total_bytes: int
    livre_bytes: int

    @property
    def pct_livre(self) -> float:
        return self.livre_bytes / self.total_bytes * 100 if self.total_bytes else 0.0


@dataclass
class Disco:
    numero: int
    nome: str
    tipo: str  # "SSD NVMe" | "SSD SATA" | "SSD" | "HDD" | "Desconhecido"
    barramento: str
    tamanho_bytes: int
    volumes: list[Volume]

    @property
    def eh_ssd(self) -> bool:
        return self.tipo.startswith("SSD")


def tipo_disco(media: str, barramento: str) -> str:
    media, barramento = media.upper(), barramento.upper()
    if barramento == "NVME":
        return "SSD NVMe"  # NVMe é sempre SSD, mesmo quando MediaType vem 'Unspecified'
    if media == "SSD":
        return "SSD SATA" if barramento == "SATA" else "SSD"
    if media == "HDD":
        return "HDD"
    return "Desconhecido"


def analisar_discos(discos: Any, particoes: Any, volumes: Any) -> list[Disco]:
    volumes_por_letra = {}
    for v in como_lista(volumes):
        letra = str(v.get("DriveLetter") or "").strip()
        if letra:
            volumes_por_letra[letra] = Volume(
                letra=letra,
                rotulo=str(v.get("FileSystemLabel") or ""),
                sistema_arquivos=str(v.get("FileSystem") or ""),
                total_bytes=int(v.get("Size") or 0),
                livre_bytes=int(v.get("SizeRemaining") or 0),
            )

    letras_por_disco: dict[int, list[str]] = {}
    for p in como_lista(particoes):
        letra = str(p.get("DriveLetter") or "").strip()
        if letra:
            letras_por_disco.setdefault(int(p.get("DiskNumber", -1)), []).append(letra)

    resultado = []
    for d in como_lista(discos):
        numero = int(d.get("DeviceId") or 0)
        barramento = str(d.get("BusType") or "")
        resultado.append(Disco(
            numero=numero,
            nome=str(d.get("FriendlyName") or "Disco").strip(),
            tipo=tipo_disco(str(d.get("MediaType") or ""), barramento),
            barramento=barramento,
            tamanho_bytes=int(d.get("Size") or 0),
            volumes=[volumes_por_letra[letra] for letra in sorted(letras_por_disco.get(numero, []))
                     if letra in volumes_por_letra],
        ))
    return sorted(resultado, key=lambda d: d.numero)
