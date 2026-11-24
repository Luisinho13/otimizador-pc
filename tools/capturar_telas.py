"""Abre o app, espera os dados carregarem e salva prints de cada tela em docs/screenshots.

Somente leitura: nenhum botão de ajuste é clicado. Uso: python tools/capturar_telas.py
A janela é exibida com a aparência do modo administrador (para os prints do README).
"""

from __future__ import annotations

import ctypes
import queue
import sys
from ctypes import wintypes
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from otimizador.core.log import configurar_log  # noqa: E402
from otimizador.ui.app import App  # noqa: E402

DESTINO = RAIZ / "docs" / "screenshots"
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def capturar_janela(hwnd: int) -> Image.Image:
    """Copia o conteúdo da janela (mesmo se houver outra janela na frente)."""
    ret = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(ret))
    largura, altura = ret.right - ret.left, ret.bottom - ret.top
    dc_janela = user32.GetWindowDC(hwnd)
    dc_mem = gdi32.CreateCompatibleDC(dc_janela)
    bitmap = gdi32.CreateCompatibleBitmap(dc_janela, largura, altura)
    gdi32.SelectObject(dc_mem, bitmap)
    user32.PrintWindow(hwnd, dc_mem, 2)  # PW_RENDERFULLCONTENT
    info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), largura, -altura, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(largura * altura * 4)
    gdi32.GetDIBits(dc_mem, bitmap, 0, altura, buffer, ctypes.byref(info), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(dc_mem)
    user32.ReleaseDC(hwnd, dc_janela)
    imagem = Image.frombuffer("RGBA", (largura, altura), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    # Remove a borda invisível que o Windows 10/11 inclui no retângulo da janela.
    return imagem.crop((7, 0, largura - 7, altura - 7)) if largura > 20 else imagem


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    fila: queue.Queue[str] = queue.Queue()
    app = App(admin=True, arquivo_log=configurar_log(fila), fila_log=fila)
    app.geometry("1200x800+40+20")

    def hwnd() -> int:
        return user32.GetParent(app.winfo_id()) or app.winfo_id()

    def pronto() -> bool:
        diag = app.telas["diagnostico"].diagnostico  # type: ignore[attr-defined]
        cartoes = app.telas["ajustes"].cartoes  # type: ignore[attr-defined]
        return diag is not None and all(c.status is not None for c in cartoes)

    passos = [("diagnostico", "01-diagnostico.png", 0.0), ("diagnostico", "02-diagnostico-memoria.png", 0.42),
              ("ajustes", "03-ajustes.png", 0.0), ("ajustes", "04-ajustes-limpeza.png", 1.0),
              ("log", "05-log.png", 0.0)]

    def rolar(tela: str, fracao: float) -> None:
        rolavel = getattr(app.telas[tela], "conteudo", None) or getattr(app.telas[tela], "lista", None)
        if rolavel is not None:
            rolavel._parent_canvas.yview_moveto(fracao)

    def executar(i: int = 0) -> None:
        if i >= len(passos):
            app.destroy()
            return
        tela, arquivo, fracao = passos[i]
        app.mostrar(tela)
        rolar(tela, fracao)
        app.update()

        def salvar() -> None:
            capturar_janela(hwnd()).save(DESTINO / arquivo, optimize=True)
            print("salvo:", arquivo)
            executar(i + 1)

        app.after(700, salvar)

    def esperar() -> None:
        if pronto():
            app.after(800, executar)
        else:
            app.after(300, esperar)

    app.after(500, esperar)
    app.mainloop()


if __name__ == "__main__":
    main()
