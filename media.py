import io
from io import BytesIO
from PIL import Image

def compress_image(data: bytes, quality: int = 40, max_px: int = 120) -> bytes:
    img = Image.open(BytesIO(data))
    img.thumbnail((max_px, max_px), Image.ANTIALIAS)
    out = BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=quality)
    return out.getvalue()

def make_video_preview(data: bytes) -> bytes | None:
    img = Image.open(BytesIO(data))