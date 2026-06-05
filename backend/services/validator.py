"""标注 JSON 校验器 — va[] 格式

校验优先级 1→9，命中第一个错误就返回：
  1-5: 红色错误 (critical)
  6-9: 黄色警告 (warning)
"""
import json


def validate_annotation_json(text: str, actual_width: int = 0, actual_height: int = 0) -> dict:
    """
    校验标注 JSON，返回 {valid, level, error}
    level: 1-5 红色, 6-9 黄色, 0 通过
    actual_width/actual_height: 实际图片宽高，用于检测 #9
    """
    # #1 不在此检测（文件不存在是调用方的责任）

    # 解析 JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"valid": False, "level": 2, "error": f"JSON 格式错误: {e}"}

    # #4 缺少 va 字段
    if not isinstance(data, dict):
        return {"valid": False, "level": 3, "error": "标注数据格式错误，缺少对象结构"}

    if "va" not in data:
        return {"valid": False, "level": 3, "error": "缺少 va 标注字段"}

    # #5 va 不是数组
    if not isinstance(data["va"], list):
        return {"valid": False, "level": 4, "error": "va 必须是数组格式"}

    # #5 va 为空数组
    if len(data["va"]) == 0:
        return {"valid": False, "level": 5, "error": "没有标注内容"}

    # #6 校验每个 entry 的 pts 存在且非空
    for i, entry in enumerate(data["va"]):
        if not isinstance(entry, dict):
            return {"valid": False, "level": 6, "error": f"va[{i}] 格式错误，缺少 pts 字段"}
        if "pts" not in entry:
            return {"valid": False, "level": 6, "error": f"va[{i}] 缺少 pts 坐标字段"}
        if not isinstance(entry["pts"], list):
            return {"valid": False, "level": 6, "error": f"va[{i}].pts 必须是数组"}
        if len(entry["pts"]) == 0:
            return {"valid": False, "level": 6, "error": f"va[{i}] 没有标注点"}

    # #7 校验每个 pts 元素的坐标完整性
    for i, entry in enumerate(data["va"]):
        for j, pt in enumerate(entry["pts"]):
            if not isinstance(pt, dict):
                return {"valid": False, "level": 7, "error": f"va[{i}].pts[{j}] 格式错误"}
            if "x" not in pt or "y" not in pt:
                return {"valid": False, "level": 7, "error": f"va[{i}].pts[{j}] 缺少 x 或 y 坐标"}

    # #8 缺少 width/height
    if "width" not in data or "height" not in data:
        return {"valid": False, "level": 8, "error": "缺少 width 或 height 字段"}

    # #9 宽高与实际图片不匹配
    if actual_width > 0 and actual_height > 0:
        if data.get("width") != actual_width or data.get("height") != actual_height:
            return {
                "valid": False, "level": 9,
                "error": f"标注宽高 {data.get('width')}x{data.get('height')} 与实际图片 {actual_width}x{actual_height} 不匹配"
            }

    return {"valid": True, "level": 0, "error": ""}
