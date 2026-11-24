"""Gera assets/icone.ico (raio branco sobre fundo azul arredondado). Uso: python tools/gerar_icone.py"""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parents[1] / "assets" / "icone.ico"
TAMANHO = 256


def desenhar() -> Image.Image:
    img = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
    fundo = Image.new("RGBA", (TAMANHO, TAMANHO))
    pixels = fundo.load()
    for y in range(TAMANHO):  # degradê diagonal azul
        for x in range(TAMANHO):
            t = (x + y) / (2 * TAMANHO)
            pixels[x, y] = (int(59 - 30 * t), int(130 - 70 * t), int(246 - 40 * t), 255)
    mascara = Image.new("L", (TAMANHO, TAMANHO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((8, 8, TAMANHO - 8, TAMANHO - 8), radius=56, fill=255)
    img.paste(fundo, (0, 0), mascara)

    raio = [(150, 30), (70, 140), (124, 140), (100, 226), (188, 106), (132, 106), (162, 30)]
    ImageDraw.Draw(img).polygon(raio, fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    desenhar().save(DESTINO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Ícone salvo em {DESTINO}")
