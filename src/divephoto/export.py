"""Export final : application du preset choisi, incrustation du crédit,
renommage et écriture des métadonnées (EXIF + mots-clés espèces)."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import piexif
from PIL import Image, ImageDraw, ImageFont

JPEG_QUALITY = 92
_FONT_CANDIDATES = ["arial.ttf", "DejaVuSans.ttf"]


def slugify(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(c if c.isalnum() else "-" for c in ascii_text.lower())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    slug = cleaned.strip("-")
    return slug[0].upper() + slug[1:] if slug else slug


def build_filename(dive_site: str, species_names: list[str], dive_date, seq: int, ext: str = ".jpg") -> str:
    """Nom de fichier : espèce(s) d'abord (le plus utile pour trier/chercher
    dans le dossier de sortie), puis lieu, date, numéro. Chaque nom (lieu,
    chaque espèce) commence par une majuscule."""
    site_slug = slugify(dive_site) or "Plongee"
    date_str = dive_date.strftime("%Y%m%d")
    species_slugs = [slugify(s) for s in species_names[:3] if slugify(s)]

    parts = list(species_slugs)
    parts.append(site_slug)
    parts.append(date_str)
    parts.append(f"{seq:04d}")
    return "_".join(parts) + ext


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_credit(rgb: np.ndarray, credit_text: str) -> np.ndarray:
    """Incruste le crédit en bas à droite, avec un contour pour rester lisible."""
    img = Image.fromarray(rgb).convert("RGB")
    draw = ImageDraw.Draw(img)
    font_size = max(16, round(img.height * 0.022))
    font = _load_font(font_size)

    margin = round(font_size * 0.8)
    bbox = draw.textbbox((0, 0), credit_text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = img.width - text_w - margin
    y = img.height - text_h - margin

    stroke_width = max(1, font_size // 12)
    draw.text(
        (x, y), credit_text, font=font, fill=(255, 255, 255),
        stroke_width=stroke_width, stroke_fill=(0, 0, 0),
    )
    return np.array(img)


def _xp_keywords_bytes(keywords: list[str]) -> bytes:
    text = ";".join(k for k in keywords if k)
    return text.encode("utf-16-le") + b"\x00\x00"


def _base_exif_dict(source_path: Path) -> dict:
    try:
        return piexif.load(str(source_path))
    except Exception:
        return {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}


def build_exif_bytes(source_path: Path, dive_site: str, species_names: list[str]) -> bytes:
    exif_dict = _base_exif_dict(source_path)
    description = dive_site if not species_names else f"{dive_site} — {', '.join(species_names)}"
    exif_dict.setdefault("0th", {})
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8", "ignore")
    exif_dict["0th"][0x9C9B] = _xp_keywords_bytes([dive_site, *species_names])  # XPKeywords (Windows)
    exif_dict.pop("thumbnail", None)
    try:
        return piexif.dump(exif_dict)
    except Exception:
        # Si des tags impossibles a re-encoder trainent dans l'EXIF source
        # (frequent avec certains firmwares), on repart d'un EXIF minimal.
        minimal = {
            "0th": {
                piexif.ImageIFD.ImageDescription: description.encode("utf-8", "ignore"),
                0x9C9B: _xp_keywords_bytes([dive_site, *species_names]),
            },
            "Exif": {}, "GPS": {}, "1st": {},
        }
        return piexif.dump(minimal)


@dataclass
class ExportResult:
    output_path: Path
    species_names: list[str]


def export_photo(
    source_path: Path,
    output_dir: Path,
    rgb_full: np.ndarray,
    preset_fn,
    dive_site: str,
    dive_date,
    photographer: str,
    species_names: list[str],
    seq: int,
) -> ExportResult:
    """Applique le preset + credit, ecrit le fichier final dans output_dir."""
    processed = preset_fn(rgb_full) if preset_fn is not None else rgb_full
    credit_text = f"{dive_site} {dive_date.year} © {photographer}"
    final = draw_credit(processed, credit_text)

    filename = build_filename(dive_site, species_names, dive_date, seq)
    output_path = output_dir / filename

    exif_bytes = build_exif_bytes(source_path, dive_site, species_names)
    Image.fromarray(final).save(output_path, quality=JPEG_QUALITY, exif=exif_bytes)

    return ExportResult(output_path=output_path, species_names=species_names)
