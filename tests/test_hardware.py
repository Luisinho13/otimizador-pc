import pytest

from otimizador.diagnostico.hardware import (analisar_cpu, analisar_discos, analisar_gpu,
                                             analisar_memoria, canal_do_pente, tipo_disco,
                                             velocidade_pelo_part_number, versao_driver_nvidia)


def test_cpu(cim_real):
    (cpu,) = analisar_cpu(cim_real["cpu"])
    assert cpu.nome == "Intel(R) Core(TM) i5-9400F CPU @ 2.90GHz"
    assert (cpu.nucleos, cpu.threads) == (6, 6)


@pytest.mark.parametrize("windows, nvidia", [
    ("32.0.16.2140", "621.40"),
    ("31.0.15.5222", "552.22"),
    ("invalida", None),
])
def test_versao_driver_nvidia(windows, nvidia):
    assert versao_driver_nvidia(windows) == nvidia


def test_gpu_prefere_nvidia_smi(cim_real):
    smi = [{"nome": "NVIDIA GeForce RTX 5060", "driver": "621.40", "vram_mib": "8151"}]
    (gpu,) = analisar_gpu(cim_real["gpu"], cim_real["gpu_vram"], smi)
    assert gpu.fabricante == "NVIDIA"
    assert gpu.driver == "621.40"
    assert gpu.vram_bytes == 8151 * 1024**2


def test_gpu_sem_nvidia_smi_converte_versao_e_usa_vram_do_registro(cim_real):
    (gpu,) = analisar_gpu(cim_real["gpu"], cim_real["gpu_vram"], [])
    assert gpu.driver == "621.40"
    assert gpu.vram_bytes == 8546942976


def test_gpu_ignora_adaptador_virtual():
    dados = [{"Name": "Microsoft Basic Display Adapter"}, {"Name": "AMD Radeon RX 7600", "PNPDeviceID": "PCI\\VEN_1002"}]
    placas = analisar_gpu(dados, None, [])
    assert [p.nome for p in placas] == ["AMD Radeon RX 7600"]
    assert placas[0].fabricante == "AMD"


@pytest.mark.parametrize("part_number, mhz", [
    ("F4-2666C15-8GVR", 2666),           # G.Skill
    ("BL8G26C16U4B.8FD", 2666),          # Crucial Ballistix
    ("CMK16GX4M2B3200C16", 3200),        # Corsair
    ("KF432C16BB/8", 3200),              # Kingston Fury
    ("F5-6000J3038F16G", 6000),          # G.Skill DDR5
    ("M378A1K43CB2-CTD", None),          # Samsung OEM: sem velocidade no código
    ("9905701-017.A00G", None),
])
def test_velocidade_pelo_part_number(part_number, mhz):
    assert velocidade_pelo_part_number(part_number) == mhz


@pytest.mark.parametrize("slot, banco, canal", [
    ("ChannelA-DIMM1", "BANK 0", "A"),    # ASUS (Intel)
    ("DIMM 1", "P0 CHANNEL B", "B"),      # placas AM4 (ex.: Gigabyte B550)
    ("DIMMA2", "BANK 0", "A"),            # MSI
    ("DIMM_B2", "", "B"),
    ("DIMM0", "BANK 0", None),
])
def test_canal_do_pente(slot, banco, canal):
    assert canal_do_pente(slot, banco) == canal


def test_memoria_real(cim_real):
    mem = analisar_memoria(cim_real["ram"], cim_real["ram_slots"])
    assert mem.total_bytes == 16 * 1024**3
    assert mem.dual_channel is True
    assert mem.mhz_atual == 2133
    assert mem.mhz_anunciado == 2666
    assert mem.abaixo_do_anunciado
    assert mem.modelos_misturados


def _pente(slot, banco="", part="KF432C16BB/8", atual=3200):
    return {"Capacity": 8 * 1024**3, "Speed": 2133, "ConfiguredClockSpeed": atual,
            "DeviceLocator": slot, "BankLabel": banco, "Manufacturer": "Kingston", "PartNumber": part}


def test_memoria_um_pente_e_single_channel():
    mem = analisar_memoria([_pente("DIMM_A2")], 4)
    assert mem.dual_channel is False
    assert not mem.abaixo_do_anunciado


def test_memoria_dois_pentes_no_mesmo_canal():
    mem = analisar_memoria([_pente("ChannelA-DIMM1"), _pente("ChannelA-DIMM2")], 4)
    assert mem.dual_channel is False
    assert "mesmo canal" in mem.canal


def test_memoria_sem_informacao_de_canal_fica_provavel():
    mem = analisar_memoria([_pente("DIMM0"), _pente("DIMM1")], 2)
    assert mem.dual_channel is None
    assert mem.canal.startswith("Provavelmente")
    assert not mem.modelos_misturados


def test_memoria_pentes_diferentes_usa_o_mais_lento():
    mem = analisar_memoria([_pente("ChannelA-DIMM1", part="F4-3600C16-8GVK", atual=2133),
                            _pente("ChannelB-DIMM1", part="KF432C16BB/8", atual=2133)], 2)
    assert mem.mhz_anunciado == 3200


@pytest.mark.parametrize("media, barramento, tipo", [
    ("SSD", "SATA", "SSD SATA"),
    ("Unspecified", "NVMe", "SSD NVMe"),
    ("HDD", "SATA", "HDD"),
    ("Unspecified", "USB", "Desconhecido"),
])
def test_tipo_disco(media, barramento, tipo):
    assert tipo_disco(media, barramento) == tipo


def test_discos_associa_volumes(cim_real):
    ssd, hdd = analisar_discos(cim_real["discos"], cim_real["particoes"], cim_real["volumes"])
    assert ssd.eh_ssd and [v.letra for v in ssd.volumes] == ["C"]
    assert not hdd.eh_ssd and [v.letra for v in hdd.volumes] == ["D"]
    assert 40 < ssd.volumes[0].pct_livre < 50
