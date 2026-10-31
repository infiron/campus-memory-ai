import re
from .embeddings import semantic_similarity_map
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from ..models import SourceRecord, Experience, Course
from .scoring import ALLOWED_RAG_PERMISSIONS, VISIBLE_PERMISSIONS, score_source, get_score_config


def tokenize(text: str) -> set[str]:
    text = (text or "").lower()
    stopwords = {"课程", "经验", "来源", "资料", "内容", "答案", "回答", "问题", "如何", "怎么", "什么", "哪些", "哪个", "请问", "请", "说明", "解释", "告诉", "一下", "关于", "这个", "那个", "可以", "是不是", "是否", "细则", "特殊", "方面", "相关", "帮助", "信息", "总结", "所有"}
    tokens = set(re.findall(r"[a-z0-9_]{2,}", text))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(chunk) <= 4:
            tokens.add(chunk)
        for size in (2, 3):
            for i in range(max(0, len(chunk) - size + 1)):
                tokens.add(chunk[i:i+size])
    return {item for item in tokens if item.strip() and item not in stopwords}


def source_content(source: SourceRecord) -> str:
    pieces = [source.title, source.course_name, source.term, source.content_excerpt]
    if source.experience:
        pieces.extend([source.experience.raw_text, source.experience.difficulty, source.experience.assignments, source.experience.assessment, source.experience.advice])
    return " ".join(piece or "" for piece in pieces)


def source_dict(db: Session, source: SourceRecord, include_content: bool = True) -> dict:
    weights, version = get_score_config(db)
    score = score_source(db, source, weights, version)
    result = {
        "id": source.id,
        "source_code": source.source_code,
        "experience_id": source.experience_id,
        "title": source.title,
        "author": source.author,
        "organization": source.organization,
        "url": source.url,
        "link_status": source.link_status if source.url else "not_applicable",
        "link_status_note": ({"unchecked": "链接尚未核验，请管理员检查；内容使用许可须独立核查。", "verified": "链接已由管理员核验。", "invalid": "链接已标记失效，已从公开检索与AI回答中移除。", "demo_placeholder": "演示占位链接，不代表真实有效出处。", "not_applicable": "平台内部稳定记录，无外部链接。"}.get(source.link_status if source.url else "not_applicable", "链接状态未知。")),
        "source_type": source.source_type,
        "school": source.school,
        "course_id": source.course_id,
        "course_name": source.course_name,
        "term": source.term,
        "claim_group": source.claim_group,
        "permission": source.permission,
        "status": source.status,
        "duplicate_of_id": source.duplicate_of_id,
        "duplicate_of_code": source.duplicate_of.source_code if source.duplicate_of else None,
        "demo_data": source.demo_data,
        "published_at": source.published_at.isoformat() if source.published_at else None,
        "experience_date": source.experience_date.isoformat() if source.experience_date else None,
        "score": score.get("score"),
        "grade": score.get("grade"),
        "score_a": score.get("score_a"),
        "score_s": score.get("score_s"),
        "score_t": score.get("score_t"),
        "score_d": score.get("score_d"),
        "most_credible": score.get("most_credible", False),
        "independent_candidates": score.get("independent_candidates", 0),
        "limitations": score.get("limitations", []),
        "rule_version": score.get("rule_version", version),
    }
    if source.permission == "link_only":
        result["permission_note"] = "该来源仅允许展示链接；平台不展示/处理其正文，不参与内容评分或AI生成。"
    if include_content and source.permission in ALLOWED_RAG_PERMISSIONS:
        result["content_excerpt"] = source.content_excerpt or ""
        if source.experience:
            result["raw_text"] = source.experience.raw_text
            result["structured"] = {
                "difficulty": source.experience.difficulty,
                "assignments": source.experience.assignments,
                "assessment": source.experience.assessment,
                "advice": source.experience.advice,
            }
    return result


def _query_base(db: Session, include_link_only: bool = True):
    allowed = list(VISIBLE_PERMISSIONS if include_link_only else ALLOWED_RAG_PERMISSIONS)
    stmt = select(SourceRecord).options(joinedload(SourceRecord.experience), joinedload(SourceRecord.duplicate_of)).where(
        SourceRecord.status == "active",
        SourceRecord.permission.in_(allowed),
    )
    return db.scalars(stmt).all()


def _course_school(db: Session, course_id: int | None) -> str | None:
    """Return the school of the selected course, or None when no course is selected."""
    if not course_id:
        return None
    course = db.get(Course, course_id)
    return course.school if course else None


def _matches_course_school(source: SourceRecord, course_id: int | None, course_school: str | None) -> bool:
    """跨校资料不能作为本校课程事实证据：来源学校必须与所选课程学校一致。

    来源学校为空且无法确认适用范围的资料也不得作为该课程事实证据。
    M2 这类外部作者但资料明确针对本校课程（school 设为本校）的来源仍按本校范围处理。
    """
    if not course_id or not course_school:
        return True
    return bool(source.school) and source.school == course_school


def search_sources(db: Session, course_id: int | None = None, term: str | None = None, query: str | None = None, limit: int = 50) -> list[dict]:
    candidates = _query_base(db, include_link_only=True)
    course_school = _course_school(db, course_id)
    q_tokens = tokenize(query or "")
    results = []
    for source in candidates:
        if source.url and source.link_status == "invalid":
            continue
        if source.duplicate_of_id is not None:
            # Reposts can be seen in the admin registry, but not as a second public result.
            continue
        if source.experience_id is not None and (not source.experience or source.experience.status != "published"):
            continue
        if course_id and source.course_id != course_id:
            continue
        if not _matches_course_school(source, course_id, course_school):
            continue
        if term and source.term.strip() != term.strip():
            continue
        content = source_content(source)
        score = 1.0
        if q_tokens:
            s_tokens = tokenize(content)
            matched = q_tokens & s_tokens
            score = len(matched) / max(len(q_tokens), 1)
            # Exact substring matches get a small boost; no unrelated results are returned.
            if query and query.lower() in content.lower():
                score += 0.35
            if score <= 0:
                continue
        item = source_dict(db, source)
        item["relevance"] = round(score, 3)
        item["navigation_only"] = source.permission == "link_only"
        results.append(item)
    results.sort(key=lambda item: (-item["relevance"], -(item["score"] or 0), item.get("published_at") or ""))
    return results[:max(1, min(limit, 100))]


async def retrieve_evidence(db: Session, question: str, course_id: int | None = None, term: str | None = None, limit: int = 6) -> list[dict]:
    candidates = _query_base(db, include_link_only=False)
    course_school = _course_school(db, course_id)
    q_tokens = tokenize(question or "")
    embedding_inputs = [(source.id, source_content(source)) for source in candidates[:80]]
    semantic_scores = await semantic_similarity_map(question or "", embedding_inputs)
    scored = []
    for source in candidates:
        if source.url and source.link_status == "invalid":
            continue
        if source.permission not in ALLOWED_RAG_PERMISSIONS or source.duplicate_of_id is not None:
            continue
        if source.experience_id is not None and (not source.experience or source.experience.status != "published"):
            continue
        if course_id and source.course_id != course_id:
            continue
        if not _matches_course_school(source, course_id, course_school):
            continue
        # With a specified term, exact-term evidence ranks first. Sources with unknown scope may supplement,
        # but are never represented as term-specific facts.
        if term and source.term and source.term.strip() != term.strip():
            continue
        content = source_content(source)
        content_tokens = tokenize(content)
        overlap = len(q_tokens & content_tokens) / max(len(q_tokens), 1) if q_tokens else 0.0
        course_bonus = 0.25 if course_id and source.course_id == course_id else 0.0
        term_bonus = 0.15 if term and source.term.strip() == term.strip() else 0.0
        # When question tokens overlap poorly, still allow a course-specific result if the user asked a broad question.
        semantic = semantic_scores.get(source.id)
        relevance = (0.55 * overlap + 0.45 * semantic if semantic is not None else overlap) + course_bonus + term_bonus
        if relevance <= 0 and not (course_id and source.course_id == course_id):
            continue
        if semantic is not None and overlap <= 0 and semantic < 0.28 and not (course_id and source.course_id == course_id):
            continue
        item = source_dict(db, source)
        item["relevance"] = round(relevance, 3)
        item["unresolved_conflict"] = source.unresolved_conflict
        if term and not source.term:
            item["scope_note"] = "该来源未注明适用学期，不能独立证明特定学期的安排。"
        scored.append(item)
    scored.sort(key=lambda item: (-item["relevance"], -(item["score"] or 0)))
    return scored[:limit]
