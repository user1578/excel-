"""跨页面共享的轻量内存工作区，不写入合并/填充业务表。"""

from __future__ import annotations

from app.models.merge_models import MergeResult
from app.models.table_dataset import Provenance, TableDataset, TableRow


class DataWorkspaceService:
    def __init__(self) -> None:
        self.current_dataset: TableDataset | None = None
        self.current_merge_result: MergeResult | None = None

    def set_merge_result(self, result: MergeResult) -> None:
        self.current_merge_result = result
        rows = []
        for index, record in enumerate(result.records, start=2):
            provenance = next(iter(record.provenance.values()), Provenance("当前汇总", "汇总结果", index))
            rows.append(TableRow(dict(record.values), provenance))
        self.current_dataset = TableDataset(
            result.columns,
            rows,
            "当前汇总",
            "汇总结果",
            1,
            column_labels=dict(result.column_labels),
        )
