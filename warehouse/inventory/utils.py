# from pathlib import Path
# from django.conf import settings

# PAD = 6  # độ dài số thứ tự

# def make_payload(sku: str, seq: int) -> str:
#     return f"{sku}-{str(seq).zfill(PAD)}"

# def save_code128_png(payload: str, title: str = "", out_dir: str | None = None) -> str:
#     from barcode import Code128
#     from barcode.writer import ImageWriter
#     base_dir = Path(out_dir) if out_dir else (Path(settings.MEDIA_ROOT) / "labels")
#     base_dir.mkdir(parents=True, exist_ok=True)
#     file_wo_ext = base_dir / payload
#     Code128(payload, writer=ImageWriter()).save(str(file_wo_ext))
#     return str(file_wo_ext) + ".png"

from pathlib import Path
from django.conf import settings

PAD = 6  # độ dài số thứ tự

def make_payload(sku: str, seq: int) -> str:
    return f"{sku}-{str(seq).zfill(PAD)}"

def _safe_filename(name: str) -> str:
    # Chỉ đổi khi ghi file/tên thư mục: "/" -> "∕" (U+2215)
    return (name or "").replace("/", "∕")

def save_code128_png(payload: str, title: str = "", out_dir: str | None = None) -> str:
    from barcode import Code128
    from barcode.writer import ImageWriter

    base_dir = Path(out_dir) if out_dir else (Path(settings.MEDIA_ROOT) / "labels")
    base_dir.mkdir(parents=True, exist_ok=True)

    # payload có thể chứa "/", phải làm an toàn tên file
    safe_stem = _safe_filename(payload)
    file_wo_ext = base_dir / safe_stem

    # Lưu barcode với nội dung gốc (payload gốc vẫn có "/")
    Code128(payload, writer=ImageWriter()).save(str(file_wo_ext))
    return str(file_wo_ext) + ".png"

