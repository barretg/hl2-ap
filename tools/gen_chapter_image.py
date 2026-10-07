"""Generate New Game's hub picture from `assets/ap_logo.png`.

The New Game dialog shows chapter 1's picture beside its title, and chapter 1
is the hub (see `mod.HUB_CHAPTER_CFG`). The classic menu draws
`materials/vgui/chapters/chapter1`, the anniversary GamepadUI menu
`materials/gamepadui/chapter1`. GamepadUI draws its whole texture (retail's
is 2048x1024); the classic menu draws only the top-left 152x86 of a 256x128
one, the rest being padding to a power of two. The square logo is centred in
the drawn area, on its own corner colour.

Written into the world's `mod/files/materials/`, committed like checkdata.txt,
so packaging needs no image library. Rerun after changing the logo.

Usage:
    python tools/gen_chapter_image.py
"""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGO = REPO_ROOT / "assets" / "ap_logo.png"
OUT = REPO_ROOT / "apworld" / "half_life_2" / "mod" / "files" / "materials"

# (texture path under materials/, texture size, the area the menu draws, the
# material's own lines). The materials repeat retail's, so each menu draws ours
# as it drew Valve's.
IMAGES = (
    ("vgui/chapters/chapter1", (256, 128), (152, 86),
     '\t"$vertexalpha" 1\r\n\t"$gammaColorRead" "1"\r\n\t"$linearWrite" "1"\r\n'),
    ("gamepadui/chapter1", (1024, 512), (1024, 512),
     '\t"$vertexcolor" 1\r\n\t"$vertexalpha" 1\r\n\t"$ignorez" 1\r\n'
     '\t"$no_fullbright" "1"\r\n'),
)

# VTF 7.2, one uncompressed BGR888 image: no mipmaps, no low-res thumbnail.
FORMAT_BGR888 = 3
FORMAT_NONE = -1
FLAGS = 0x4 | 0x8 | 0x100 | 0x200  # clamp s, clamp t, no mip, no lod
HEADER_SIZE = 80


def vtf(image: Image.Image) -> bytes:
    width, height = image.size
    header = struct.pack(
        "<4s2IIHHIHH4x3f4xfiBiBBH",
        b"VTF\0", 7, 2, HEADER_SIZE, width, height, FLAGS,
        1, 0,                 # frames, first frame
        0.5, 0.5, 0.5,        # reflectivity
        1.0,                  # bump scale
        FORMAT_BGR888, 1,     # format, mipmap count
        FORMAT_NONE, 0, 0,    # low-res thumbnail: none
        1,                    # depth
    )
    header = header.ljust(HEADER_SIZE, b"\0")
    r, g, b = image.convert("RGB").split()
    return header + Image.merge("RGB", (b, g, r)).tobytes()


def framed(logo: Image.Image, size: tuple[int, int], drawn: tuple[int, int]) -> Image.Image:
    logo = logo.convert("RGB")
    canvas = Image.new("RGB", size, logo.getpixel((0, 0)))
    width, height = drawn
    side = min(width, height)
    scaled = logo.resize((side, side), Image.LANCZOS)
    canvas.paste(scaled, ((width - side) // 2, (height - side) // 2))
    return canvas


def main() -> int:
    logo = Image.open(LOGO)
    for texture, size, drawn, material in IMAGES:
        target = OUT / f"{texture}.vtf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(vtf(framed(logo, size, drawn)))
        (OUT / f"{texture}.vmt").write_bytes(
            f'"UnlitGeneric"\r\n{{\r\n\t"$basetexture" "{texture}"\r\n{material}}}\r\n'.encode())
        print(f"wrote {target.relative_to(REPO_ROOT)} ({size[0]}x{size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
