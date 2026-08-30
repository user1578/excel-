"""xlsx/csv 只读加载器，不修改源文件。"""
from pathlib import Path
import pandas as pd

SUPPORTED={".xlsx",".csv"}
def list_sheets(path:Path)->list[str]:
    if path.suffix.lower()==".csv": return []
    if path.suffix.lower()!=".xlsx": raise ValueError("仅支持 .xlsx 和 .csv 文件")
    try: return pd.ExcelFile(path,engine="openpyxl").sheet_names
    except Exception as e: raise ValueError(f"无法读取 Excel 文件：{e}") from e
def read_raw(path:Path,sheet_name:str|None=None)->pd.DataFrame:
    if not path.exists(): raise ValueError("文件不存在")
    ext=path.suffix.lower()
    if ext==".xlsx":
        try: frame=pd.read_excel(path,sheet_name=sheet_name or 0,header=None,dtype=object,engine="openpyxl")
        except Exception as e: raise ValueError(f"无法读取 Excel 文件：{e}") from e
    elif ext==".csv":
        for encoding in ("utf-8-sig","gbk","utf-8"):
            try: frame=pd.read_csv(path,header=None,dtype=object,encoding=encoding); break
            except UnicodeDecodeError: continue
        else: raise ValueError("CSV 编码无法识别")
    else: raise ValueError("仅支持 .xlsx 和 .csv 文件")
    if frame.empty: raise ValueError("文件或工作表为空")
    return frame
