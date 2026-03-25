from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def make_preview(path: Path, title: str, subtitle: str, size: tuple[int, int] = (1024, 1024)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=(22, 26, 36))
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arial.ttf", 46)
        body_font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rectangle([(24, 24), (size[0] - 24, size[1] - 24)], outline=(110, 170, 255), width=4)
    draw.text((60, 70), title, fill=(235, 240, 255), font=title_font)
    draw.text((60, 150), subtitle, fill=(180, 195, 225), font=body_font)
    notes = [
        "preview placeholder",
        "replace later with real Unreal validation-map captures",
        "keep file names stable for the catalog pipeline",
    ]
    y = 260
    for line in notes:
        draw.text((60, y), line, fill=(160, 170, 190), font=body_font)
        y += 42
    image.save(path)


def generate_asset_preview_set(asset_id: str, preview_root: Path = Path("data/previews")) -> None:
    asset_dir = preview_root / asset_id
    make_preview(asset_dir / "front.png", asset_id, "front view")
    make_preview(asset_dir / "angle.png", asset_id, "angle view")
    make_preview(asset_dir / "top.png", asset_id, "top view")


if __name__ == "__main__":
    generate_asset_preview_set("sm_modern_sofa_a")
