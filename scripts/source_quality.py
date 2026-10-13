"""Source identity and freshness checks shared by selection and publication."""
from datetime import date
import calendar
import re
from urllib.parse import urlparse

EFFECTIVE_DATE = "2026-10-12"
HISTORICAL = re.compile(r"歷史(?:參考|版本)|舊文回顧")
GENERIC_ANALYSIS = (
    "可挑與目前作品相近的鏡頭或素材做小型比較",
    "可用自己的角色試做姿勢與動作",
    "可選一個角色或道具測試貼圖與材質",
    "可拿一個現有模型試做",
    "目前簡介不足以確認完整實作與效能",
)


def dated_url_upper_bound(url):
    """Use month end: a URL month is not evidence of a precise publication day."""
    match = re.search(r"/(20\d{2})/(\d{2})(?:/|$)", urlparse(url).path)
    if not match:
        return None
    year, month = map(int, match.groups())
    try:
        return date(year, month, calendar.monthrange(year, month)[1])
    except ValueError:
        return None


def source_quality_errors(item, report_date):
    if report_date < EFFECTIVE_DATE:
        return []
    errors = []
    url = str(item.get("source_url") or "")
    path = urlparse(url).path.rstrip("/").lower()
    industry_index = path.startswith("/industries/") and len(path.strip("/").split("/")) == 2
    if path in {"/articles/game-development", "/download/requirements"} or industry_index:
        errors.append("source is an index, requirements or industry landing page")
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    published = item.get("source_published_at")
    source_date = None
    if published:
        try:
            source_date = date.fromisoformat(published)
        except (TypeError, ValueError):
            errors.append("invalid source publication date")
    # A refreshed metadata timestamp cannot turn an old URL into a new release.
    # Substantive updates require editorial context rather than a freshness bypass.
    url_date = dated_url_upper_bound(url)
    if url and not source_date and not url_date:
        errors.append("source date is unverified; do not silently treat it as evergreen")
    dates = [value for value in (source_date, url_date) if value]
    upper_bound = min(dates) if dates else None
    if source_date and source_date > date.fromisoformat(report_date):
        errors.append("source postdates the requested edition")
    elif url_date and url_date.replace(day=1) > date.fromisoformat(report_date):
        errors.append("source URL month postdates the requested edition")
    if upper_bound:
        age = (date.fromisoformat(report_date) - upper_bound).days
        if age > 180 and not (HISTORICAL.search(title) and str(upper_bound.year) in summary):
            errors.append("old source requires an explicit historical title and source year in summary")
    visible = "\n".join(str(b.get("text") or "") for b in item.get("full_analysis", []))
    if any(phrase in visible for phrase in GENERIC_ANALYSIS):
        errors.append("generic analysis padding is not source-specific evidence")
    return errors
