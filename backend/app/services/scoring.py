from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import SourceRecord, SystemSetting

DEFAULT_WEIGHTS = {"A": 0.40, "S": 0.25, "T": 0.20, "D": 0.15}
DEFAULT_RULE_VERSION = "V1.0"
ALLOWED_RAG_PERMISSIONS = {"abstract_allowed", "full_text_allowed"}
VISIBLE_PERMISSIONS = ALLOWED_RAG_PERMISSIONS | {"link_only"}


def get_score_config(db: Session, version: str | None = None) -> tuple[dict, str]:
    if version:
        archived = db.scalar(select(SystemSetting).where(SystemSetting.key == f"score_weights_{version}"))
        if archived:
            return archived.value or DEFAULT_WEIGHTS.copy(), archived.version or version
        current = db.scalar(select(SystemSetting).where(SystemSetting.key == "score_weights"))
        if current and current.version == version:
            return current.value or DEFAULT_WEIGHTS.copy(), current.version or version
        return DEFAULT_WEIGHTS.copy(), version
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "score_weights"))
    if not setting:
        return DEFAULT_WEIGHTS.copy(), DEFAULT_RULE_VERSION
    return setting.value or DEFAULT_WEIGHTS.copy(), setting.version or DEFAULT_RULE_VERSION


def _source_date(source: SourceRecord) -> datetime | None:
    return source.experience_date or source.published_at


def _full_months_between(earlier: datetime, later: datetime) -> int:
    months = (later.year - earlier.year) * 12 + later.month - earlier.month
    if later.day < earlier.day:
        months -= 1
    return max(months, 0)


def _time_score(source: SourceRecord, now: datetime) -> float:
    created = _source_date(source)
    if created is None:
        return 30.0
    months = _full_months_between(created, now)
    if months <= 6:
        score = 100.0
    elif months <= 12:
        score = 80.0
    elif months <= 24:
        score = 60.0
    else:
        score = 30.0
    if source.major_course_change:
        return 30.0
    return score


def _completeness_score(source: SourceRecord) -> float:
    score = 0.0
    # The course field is meaningful only when the source is assigned to a course.
    if source.course_name.strip():
        score += 20
    if source.term.strip():
        score += 20
    if source.has_concrete_scenario:
        score += 30
    if source.has_actionable_detail:
        score += 30
    return score


def _traceability_score(source: SourceRecord) -> float:
    score = 0.0
    # A stable record ID is acceptable for internal experiences; external items need a URL.
    if (source.experience_id is not None and source.id is not None) or source.url.strip():
        score += 40
    if source.author_verified or source.organization.strip():
        score += 20
    if source.source_type.strip():
        score += 20
    if source.permission in ALLOWED_RAG_PERMISSIONS:
        score += 20
    return min(score, 100.0)


def _eligible_for_scoring(source: SourceRecord) -> bool:
    return (source.status == "active" and source.permission in ALLOWED_RAG_PERMISSIONS
            and source.duplicate_of_id is None and not (source.url and source.link_status == "invalid"))


def score_source(db: Session, source: SourceRecord, weights: dict | None = None, rule_version: str = DEFAULT_RULE_VERSION, now: datetime | None = None) -> dict:
    weights = weights or DEFAULT_WEIGHTS
    if not _eligible_for_scoring(source):
        reason = "转载已归并，不重复评分" if source.duplicate_of_id else "来源状态或使用权限不允许评分"
        return {
            "source_id": source.id, "source_code": source.source_code, "title": source.title,
            "score_a": None, "score_s": None, "score_t": None, "score_d": None,
            "score": None, "grade": "不计分", "most_credible": False,
            "independent_candidates": 0, "limitations": [reason], "rule_version": rule_version,
        }

    now = now or source.score_reference_date or datetime.now(timezone.utc).replace(tzinfo=None)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    group_stmt = select(SourceRecord).where(
        SourceRecord.school == source.school,
        SourceRecord.course_name == source.course_name,
        SourceRecord.claim_group == source.claim_group,
        SourceRecord.status == "active",
        SourceRecord.permission.in_(list(ALLOWED_RAG_PERMISSIONS)),
        SourceRecord.duplicate_of_id.is_(None),
    )
    group = [item for item in db.scalars(group_stmt).all() if not (item.url and item.link_status == "invalid")]
    # Counting the same source only once is enforced by excluding duplicate_of records above.
    n = len({item.id for item in group})
    if source.unresolved_conflict:
        a = 20.0
    elif source.current_official_fact:
        a = 80.0
    elif n >= 3:
        a = 100.0
    elif n == 2:
        a = 80.0
    else:
        a = 50.0
    s = _traceability_score(source)
    t = _time_score(source, now)
    d = _completeness_score(source)
    total = round(weights["A"] * a + weights["S"] * s + weights["T"] * t + weights["D"] * d, 1)

    limitations: list[str] = []
    if n <= 1:
        limitations.append("独立来源单一，样本有限")
    if not source.term:
        limitations.append("未注明经历学期或适用时间")
    if not source.author_verified and not source.organization:
        limitations.append("作者或机构缺少可核验信息")
    if source.unresolved_conflict:
        limitations.append("存在未解决的实质性冲突")
    if total >= 80 and (n >= 2 or source.current_official_fact) and not source.unresolved_conflict:
        grade = "较高"
    elif total >= 60:
        grade = "中等"
    else:
        grade = "较低"
    # A single subjective student experience cannot be rated above medium, regardless of total.
    if source.source_type == "student_experience" and n <= 1 and not source.current_official_fact and grade == "较高":
        grade = "中等"

    # The top label requires multiple distinct candidates in the same claim scope and complete evidence.
    candidates = [item for item in group if _eligible_for_scoring(item)]
    candidate_scores = []
    for item in candidates:
        item_n = len({x.id for x in group})
        item_a = 20.0 if item.unresolved_conflict else (80.0 if item.current_official_fact else (100.0 if item_n >= 3 else 80.0 if item_n == 2 else 50.0))
        item_s = _traceability_score(item)
        item_t = _time_score(item, item.score_reference_date or now)
        item_d = _completeness_score(item)
        item_total = round(weights["A"]*item_a + weights["S"]*item_s + weights["T"]*item_t + weights["D"]*item_d, 1)
        candidate_scores.append((item, item_total))
    candidate_scores.sort(key=lambda pair: (-pair[1], -int(pair[0].author_verified), -((_source_date(pair[0]) or datetime.min).toordinal()), -_traceability_score(pair[0])))
    top_id = candidate_scores[0][0].id if candidate_scores else None
    enough_critical_evidence = bool(source.course_name.strip() and source.source_type.strip() and source.permission in ALLOWED_RAG_PERMISSIONS and _source_date(source))
    no_group_conflict = not any(item.unresolved_conflict for item in group)
    independent_candidates = len({item.id for item in candidates})
    most_credible = bool(
        source.id == top_id and independent_candidates >= 2 and total >= 60
        and no_group_conflict and enough_critical_evidence
    )
    if any(item.unresolved_conflict for item in group):
        limitations.append("同一范围存在未解决冲突，取消最可信标签")
    if independent_candidates < 2:
        limitations.append("至少需要两个独立候选才能标注最可信参考")
    return {
        "source_id": source.id, "source_code": source.source_code, "title": source.title,
        "school": source.school, "course_name": source.course_name, "term": source.term, "claim_group": source.claim_group, "source_type": source.source_type,
        "permission": source.permission, "status": source.status, "duplicate_of_id": source.duplicate_of_id,
        "score_a": a, "score_s": s, "score_t": t, "score_d": d,
        "score": total, "grade": grade, "most_credible": most_credible,
        "independent_candidates": independent_candidates, "limitations": limitations,
        "rule_version": rule_version, "score_reference_date": now.date().isoformat(),
        "content_excerpt": source.content_excerpt, "url": source.url,
        "demo_data": source.demo_data,
    }


def score_sources(db: Session, sources: list[SourceRecord]) -> list[dict]:
    weights, version = get_score_config(db)
    scored = [score_source(db, source, weights, version) for source in sources]
    # Sort by score while leaving unscored reposts after scored records.
    scored.sort(key=lambda item: (item["score"] is None, -(item["score"] or 0), item.get("source_code") or ""))
    # Reapply the top label within each group: only one source may earn it.
    best_by_scope: dict[tuple, dict] = {}
    for row in scored:
        if row["score"] is None:
            row["most_credible"] = False
            continue
        scope = (row.get("school"), row.get("course_name"), row.get("claim_group"))
        if row["most_credible"]:
            if scope in best_by_scope:
                row["most_credible"] = False
            else:
                best_by_scope[scope] = row
    return scored
