"""Jarvis ikonlarini (PNG + ICO) uretir. Calistir: python tools/make_icons.py"""
import os
from PIL import Image, ImageDraw

OUT_ICONS = os.path.join("public", "icons")
ICO_PATH = os.path.join("public", "icons", "jarvis.ico")


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_icon(size):
    S = size * 4
    c = S / 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Arka plan: yuvarlak koseli, radyal koyu mavi
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    for i in range(80, 0, -1):
        t = i / 80
        rad = c * t
        col = lerp((10, 38, 52), (1, 10, 15), 1 - t)
        bd.ellipse([c - rad, c - rad, c + rad, c + rad], fill=col + (255,))

    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(bg, (0, 0), mask)

    d = ImageDraw.Draw(img)

    # Dis halkalar
    d.ellipse([c - S * 0.30, c - S * 0.30, c + S * 0.30, c + S * 0.30],
              outline=(47, 214, 255, 90), width=max(2, int(S * 0.012)))
    d.ellipse([c - S * 0.235, c - S * 0.235, c + S * 0.235, c + S * 0.235],
              outline=(47, 214, 255, 140), width=max(2, int(S * 0.010)))
    d.ellipse([c - S * 0.175, c - S * 0.175, c + S * 0.175, c + S * 0.175],
              outline=(47, 214, 255, 180), width=max(1, int(S * 0.008)))

    # Isik halesi
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    core_r = S * 0.115
    for i in range(int(S * 0.18), int(core_r), -1):
        t = (i - core_r) / (S * 0.18 - core_r)
        gd.ellipse([c - i, c - i, c + i, c + i], fill=(47, 214, 255, int(70 * (1 - t))))
    img.alpha_composite(glow)

    # Cekirdek
    d = ImageDraw.Draw(img)
    for i in range(int(core_r), 0, -1):
        t = i / core_r
        col = lerp((191, 243, 255), (22, 169, 214), t)
        d.ellipse([c - i, c - i, c + i, c + i], fill=col + (255,))

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT_ICONS, exist_ok=True)
    sizes = {"icon-192.png": 192, "icon-512.png": 512, "icon-384.png": 384,
             "icon-152.png": 152, "icon-144.png": 144}
    for name, sz in sizes.items():
        draw_icon(sz).save(os.path.join(OUT_ICONS, name))
        print("yazildi:", name)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img = draw_icon(256)
    img.save(ICO_PATH, format="ICO", sizes=ico_sizes)
    print("yazildi:", ICO_PATH)


if __name__ == "__main__":
    main()
