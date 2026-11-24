import _winapi
import os
import time

from otimizador.ajustes.limpeza import AlvoLimpeza, Limpeza, limpar, medir
from otimizador.core.estado import Estado
from otimizador.core.formato import tamanho


def _arquivo(caminho, tamanho_bytes, idade_s=0):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"x" * tamanho_bytes)
    if idade_s:
        antigo = time.time() - idade_s
        os.utime(caminho, (antigo, antigo))


def test_limpeza_respeita_idade_minima(tmp_path):
    _arquivo(tmp_path / "velho.tmp", 100, idade_s=2 * 86400)
    _arquivo(tmp_path / "sub" / "velho2.tmp", 50, idade_s=2 * 86400)
    _arquivo(tmp_path / "novo.tmp", 1000)
    alvo = AlvoLimpeza("t", "Teste", [tmp_path], idade_minima_s=86400)

    assert medir(alvo).bytes == 150
    res = limpar(alvo)
    assert res.liberado == 150 and res.apagados == 2
    assert (tmp_path / "novo.tmp").exists()
    assert not (tmp_path / "sub").exists()  # pasta vazia removida


def test_limpeza_nao_segue_junction(tmp_path):
    importante = tmp_path / "importante"
    _arquivo(importante / "documento.txt", 10)
    cache = tmp_path / "cache"
    _arquivo(cache / "shader.bin", 20)
    _winapi.CreateJunction(str(importante), str(cache / "link"))

    res = limpar(AlvoLimpeza("c", "Cache", [cache]))
    assert res.liberado == 20
    assert (importante / "documento.txt").exists()


def test_ajuste_limpeza_lista_so_pastas_existentes(tmp_path):
    _arquivo(tmp_path / "a" / "x.bin", 2048)
    alvos = [AlvoLimpeza("a", "Existe", [tmp_path / "a"]), AlvoLimpeza("b", "Não existe", [tmp_path / "b"])]
    ajuste = Limpeza(Estado(tmp_path / "estado.json"), alvos)
    status = ajuste.status()
    assert [o.id for o in status.opcoes] == ["a"]
    resultado = ajuste.aplicar({"a"})
    assert resultado.sucesso and "2,0 KB" in resultado.mensagem


def test_estado_guarda_somente_o_primeiro_valor(tmp_path):
    estado = Estado(tmp_path / "estado.json")
    estado.guardar_original("plano", "equilibrado")
    estado.guardar_original("plano", "alto")  # segunda aplicação não sobrescreve
    assert Estado(tmp_path / "estado.json").original("plano") == "equilibrado"
    estado.descartar("plano")
    assert not Estado(tmp_path / "estado.json").tem("plano")


def test_formato_tamanho():
    assert tamanho(0) == "0 B"
    assert tamanho(1536) == "1,5 KB"
    assert tamanho(5 * 1024**3) == "5,0 GB"
    assert tamanho(1300 * 1024**3) == "1,3 TB"
