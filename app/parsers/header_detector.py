"""基于规则的表头行检测。"""
import pandas as pd
from app.parsers.field_detector import ALIASES

KEYWORDS={word for words in ALIASES.values() for word in words}
def detect_header(frame:pd.DataFrame, limit:int=10)->tuple[int,int,str]:
    if frame.empty: raise ValueError("文件或工作表为空")
    best=(0,-999,"未找到可用表头")
    for row_index in range(min(limit,len(frame))):
        values=[str(v).strip() for v in frame.iloc[row_index].tolist() if pd.notna(v) and str(v).strip()]
        if not values: continue
        hits=sum(v in KEYWORDS for v in values); text=sum(not v.replace('.','',1).isdigit() for v in values)
        score=hits*20+len(values)*3+text
        if len(values)==1 and hits==0: score-=30
        if row_index+1<len(frame) and len(frame.iloc[row_index+1].dropna())>=max(2,len(values)-1): score+=3
        if score>best[1]: best=(row_index,score,f"关键词命中{hits}个，非空单元格{len(values)}个")
    if best[1]<0: raise ValueError("无法判断表头行，请手动选择")
    return best
