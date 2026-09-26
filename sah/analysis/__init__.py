"""每家公司的分析數據（供 APP／報表直接使用）。"""
from .company import COMPANY_COLUMNS, analyze_company

__all__ = ["analyze_company", "COMPANY_COLUMNS"]
