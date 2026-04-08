"""ビルド時に printer_icon.ico を生成するスクリプト"""
from PIL import Image, ImageDraw


def make_printer_icon(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 256  # スケール係数

    # 色定義
    body_color  = (52, 120, 196)   # 青系プリンター本体
    dark_blue   = (35,  85, 145)   # 影・帯
    paper_white = (255, 255, 255)
    paper_edge  = (190, 190, 190)
    green_led   = (46,  204,  90)
    line_gray   = (170, 170, 170)

    def sc(v):
        return int(v * s)

    # ── プリンター本体 ──────────────────────────────────────
    draw.rounded_rectangle(
        [sc(18), sc(82), sc(238), sc(182)],
        radius=sc(18), fill=body_color
    )

    # 本体上部の暗い帯（奥行き感）
    draw.rounded_rectangle(
        [sc(18), sc(82), sc(238), sc(108)],
        radius=sc(18), fill=dark_blue
    )

    # 用紙スロット（本体内の暗い横線）
    draw.rounded_rectangle(
        [sc(50), sc(138), sc(206), sc(158)],
        radius=sc(4), fill=dark_blue
    )

    # ── 上トレイ（入力用紙） ────────────────────────────────
    draw.rounded_rectangle(
        [sc(72), sc(28), sc(184), sc(102)],
        radius=sc(6), fill=paper_white, outline=paper_edge, width=sc(2)
    )
    # 用紙の横線
    for y in [sc(52), sc(64), sc(76), sc(88)]:
        draw.line([sc(86), y, sc(170), y], fill=line_gray, width=max(1, sc(2)))

    # ── 下トレイ（出力用紙） ────────────────────────────────
    draw.rounded_rectangle(
        [sc(62), sc(158), sc(194), sc(228)],
        radius=sc(6), fill=paper_white, outline=paper_edge, width=sc(2)
    )
    # 用紙の横線
    for y in [sc(176), sc(189), sc(202), sc(215)]:
        draw.line([sc(78), y, sc(178), y], fill=line_gray, width=max(1, sc(2)))

    # ── ステータスLED（緑） ─────────────────────────────────
    draw.ellipse(
        [sc(192), sc(100), sc(218), sc(126)],
        fill=green_led
    )
    # LEDの光沢
    draw.ellipse(
        [sc(196), sc(103), sc(208), sc(113)],
        fill=(200, 255, 210, 180)
    )

    return img


def main():
    base = make_printer_icon(256)
    sizes = [16, 32, 48, 64, 128, 256]
    images = [base.resize((sz, sz), Image.LANCZOS) for sz in sizes]
    images[0].save(
        "printer_icon.ico",
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[1:],
    )
    print("printer_icon.ico generated.")


if __name__ == "__main__":
    main()
