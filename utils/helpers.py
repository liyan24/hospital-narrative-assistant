from datetime import datetime


def timestamp() -> str:
    """返回当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_json(data) -> dict:
    """安全地将数据转为可JSON序列化的字典"""
    if hasattr(data, "_mapping"):
        return dict(data._mapping)
    if hasattr(data, "dict"):
        return data.dict()
    if isinstance(data, (list, tuple)):
        return [safe_json(item) for item in data]
    return data
