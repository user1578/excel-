"""受限插入用户照片的共享帮助器。"""

from __future__ import annotations

from pathlib import Path

from openpyxl.drawing.image import Image as ExcelImage
from PIL import Image as PillowImage


class PhotoInsertError(ValueError):
    def __init__(self, field_name: str, row_number: int, path: str | Path) -> None:
        self.field_name = field_name
        self.row_number = row_number
        self.path = Path(path)
        super().__init__(f"照片字段“{field_name}”第 {row_number} 行无法插入图片：{self.path}")


def constrained_photo(path: str | Path, max_width: float, max_height: float, field_name: str, row_number: int) -> tuple[Path, int, int]:
    source = Path(path)
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not source.is_file():
        raise PhotoInsertError(field_name, row_number, source)
    try:
        with PillowImage.open(source) as image:
            width, height = image.size
    except (OSError, ValueError) as error:
        raise PhotoInsertError(field_name, row_number, source) from error
    if width <= 0 or height <= 0:
        raise PhotoInsertError(field_name, row_number, source)
    scale = min(max_width / width, max_height / height, 1)
    return source, max(1, int(width * scale)), max(1, int(height * scale))


def insert_limited_photo(sheet, cell, path: str | Path, field_name: str, row_number: int) -> None:
    column_width = sheet.column_dimensions[cell.column_letter].width or 8.43
    row_height = sheet.row_dimensions[cell.row].height or 15
    source, width, height = constrained_photo(path, column_width * 7, row_height * 96 / 72, field_name, row_number)
    image = ExcelImage(str(source))
    image.width = width
    image.height = height
    sheet.add_image(image, cell.coordinate)
