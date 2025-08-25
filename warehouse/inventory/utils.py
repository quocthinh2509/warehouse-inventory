from pathlib import Path
from django.conf import settings

PAD = 6  # độ dài số thứ tự

def make_payload(sku: str, seq: int) -> str:
    return f"{sku}-{str(seq).zfill(PAD)}"

def save_code128_png(payload: str, title: str = "", out_dir: str | None = None) -> str:
    from barcode import Code128
    from barcode.writer import ImageWriter
    base_dir = Path(out_dir) if out_dir else (Path(settings.MEDIA_ROOT) / "labels")
    base_dir.mkdir(parents=True, exist_ok=True)
    file_wo_ext = base_dir / payload
    Code128(payload, writer=ImageWriter()).save(str(file_wo_ext))
    return str(file_wo_ext) + ".png"
