"""资料汇总的结果、冲突与人工解决模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models.table_dataset import Provenance


class MergeMode(str, Enum):
    VERTICAL = "vertical"
    STUDENT = "student"


class ConflictResolution(str, Enum):
    UNRESOLVED = "unresolved"
    USE_A = "use_a"
    USE_B = "use_b"
    MANUAL = "manual"


@dataclass
class MergedRecord:
    values: dict[str, Any]
    provenance: dict[str, Provenance] = field(default_factory=dict)
    match_status: str = "matched"


@dataclass
class MergeConflict:
    id: int
    record_index: int
    field: str
    value_a: Any
    value_b: Any
    source_a: Provenance
    source_b: Provenance
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED
    resolved_value: Any | None = None

    @property
    def is_resolved(self) -> bool:
        return self.resolution is not ConflictResolution.UNRESOLVED


@dataclass
class MergeResult:
    mode: MergeMode
    columns: list[str]
    column_labels: dict[str, str]
    records: list[MergedRecord]
    conflicts: list[MergeConflict] = field(default_factory=list)
    unresolved_record_indexes: list[int] = field(default_factory=list)
    source_datasets: list[tuple[str, str | None]] = field(default_factory=list)

    @property
    def unresolved_conflicts(self) -> list[MergeConflict]:
        return [item for item in self.conflicts if not item.is_resolved]

    @property
    def resolved_conflicts(self) -> list[MergeConflict]:
        return [item for item in self.conflicts if item.is_resolved]
