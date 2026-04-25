"""
JEC-QA 科目 / CAIL 案情 → 法律领域（legal_domain）短码。
无需修改原始数据集；调整映射只需改本文件中的规则顺序或条目。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

LEGAL_DOMAIN_OPTIONS: List[Tuple[str, str]] = [
    ("", "综合（不限法律领域）"),
    ("xingfa", "刑法"),
    ("minfa", "民法"),
    ("xingzhengfa", "行政法与行政诉讼"),
    ("susongfa", "民事/刑事诉讼法"),
    ("jingjifa", "经济法"),
    ("guojifa", "国际法与国际私法"),
    ("lilunfa", "法理与法治理论"),
    ("qita", "其它科目"),
]

LEGAL_DOMAIN_LABELS = {code: label for code, label in LEGAL_DOMAIN_OPTIONS if code}

_JEC_SUBJECT_RULES: List[Tuple[str, str]] = [
    ("中国特色社会主义法治理论", "lilunfa"),
    ("行政法与行政诉讼法", "xingzhengfa"),
    ("民事诉讼法", "susongfa"),
    ("刑事诉讼法", "susongfa"),
    ("国际私法", "guojifa"),
    ("国际法", "guojifa"),
    ("环境资源法", "qita"),
    ("司法制度与法律职业道德", "lilunfa"),
    ("法理学", "lilunfa"),
    ("经济法", "jingjifa"),
    ("商法", "jingjifa"),
    ("民法", "minfa"),
    ("刑法", "xingfa"),
    ("行政法", "xingzhengfa"),
]


def map_jec_subject_to_domain(subject: Optional[str]) -> str:
    s = (subject or "").strip()
    if not s:
        return "qita"
    for key, domain in _JEC_SUBJECT_RULES:
        if key in s:
            return domain
    return "qita"


def map_cail_to_domain(_charge_label: Optional[str]) -> str:
    return "xingfa"


def normalize_legal_domain_for_filter(legal_domain: Optional[str]) -> Optional[str]:
    if legal_domain is None:
        return None
    t = str(legal_domain).strip()
    if not t:
        return None
    valid = {code for code, _ in LEGAL_DOMAIN_OPTIONS if code}
    if t not in valid:
        return None
    return t
