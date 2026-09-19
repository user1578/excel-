"""工作簿输出的同目录原子提交事务。"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


class AtomicFileOutput:
    def __init__(self, source_path: Path | None, output_path: str | Path) -> None:
        self.source_path = Path(source_path) if source_path is not None else None
        self.output_path = Path(output_path)
        if self.source_path is not None and self.source_path.resolve() == self.output_path.resolve():
            raise ValueError("不能覆盖源模板，请选择其他输出路径。")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.temporary_path = self.output_path.with_name(
            f"{self.output_path.stem}.partial.{uuid4().hex}{self.output_path.suffix}"
        )

    def __enter__(self) -> "AtomicFileOutput":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.cleanup()

    def commit(self, validate) -> Path:
        try:
            if not self.temporary_path.exists():
                raise RuntimeError("临时输出文件不存在。")
            if validate(self.temporary_path) is False:
                raise ValueError("输出文件校验失败。")
            os.replace(self.temporary_path, self.output_path)
            return self.output_path
        except Exception:
            self.cleanup()
            raise

    def cleanup(self) -> None:
        if self.temporary_path.exists():
            self.temporary_path.unlink()


AtomicWorkbookOutput = AtomicFileOutput
