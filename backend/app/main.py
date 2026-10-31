from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import re
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .database import Base, engine, get_db, SessionLocal, ensure_schema_compatibility
from .models import (User, Course, Experience, SourceRecord, AnswerRecord, EvidenceLink,
                     ReviewLog, Feedback, OperationLog, SystemSetting, utcnow)
from .security import get_current_user, require_roles, issue_token, verify_password, serialize_user
from .seed import seed_database
from .services.ai import extract_experience, answer_from_evidence
from .services.retrieval import search_sources, retrieve_evidence, source_dict
from .services.scoring import score_sources, score_source, get_score_config, DEFAULT_WEIGHTS, ALLOWED_RAG_PERMISSIONS, VISIBLE_PERMISSIONS

STATIC_DIR = Path(__file__).resolve().parent / "static"

class LoginRequest(BaseModel):
    username: str
    password: str

class ExperienceCreate(BaseModel):
    course_id: int
    term: str = Field(min_length=1, max_length=80)
    raw_text: str = Field(min_length=8, max_length=12000)
    author_visibility: Literal["anonymous", "display_name"] = "anonymous"

class ExperienceEdit(BaseModel):
    raw_text: str | None = Field(default=None, min_length=8, max_length=12000)
    difficulty: str = Field(default="未提及", max_length=4000)
    assignments: str = Field(default="未提及", max_length=4000)
    assessment: str = Field(default="未提及", max_length=4000)
    advice: str = Field(default="未提及", max_length=4000)

class ConfirmExperience(ExperienceEdit):
    confirm: bool = True

class ReviewAction(BaseModel):
    action: Literal["approve", "return", "reject", "unpublish"]
    reason: str = Field(default="", max_length=2000)
    claim_group: str = Field(default="", max_length=180)
    unresolved_conflict: bool = False
    major_course_change: bool = False

class SourceCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    author: str = Field(default="", max_length=200)
    organization: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)
    source_type: Literal["external_answer", "official_document", "student_experience", "other"] = "external_answer"
    school: str = Field(default="", max_length=160)
    course_id: int | None = None
    course_name: str = Field(default="", max_length=160)
    term: str = Field(default="", max_length=80)
    claim_group: str = Field(min_length=2, max_length=180)
    content_excerpt: str = Field(default="", max_length=12000)
    permission: Literal["link_only", "abstract_allowed", "full_text_allowed", "pending", "prohibited"] = "pending"
    author_verified: bool = False
    official: bool = False
    current_official_fact: bool = False
    major_course_change: bool = False
    unresolved_conflict: bool = False
    has_concrete_scenario: bool = False
    has_actionable_detail: bool = False
    experience_date: str | None = None
    published_at: str | None = None
    obtained_at: str | None = None
    duplicate_of_id: int | None = None
    confirm_reviewed: bool = False

class PermissionUpdate(BaseModel):
    permission: Literal["link_only", "abstract_allowed", "full_text_allowed", "pending", "prohibited"]
    reason: str = Field(min_length=2, max_length=2000)
    content_excerpt: str | None = Field(default=None, max_length=12000)
    confirm_reviewed: bool = False

class LinkStatusUpdate(BaseModel):
    link_status: Literal["unchecked", "verified", "invalid"]
    reason: str = Field(min_length=2, max_length=2000)

class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    course_id: int | None = None
    term: str | None = Field(default=None, max_length=80)

class FeedbackCreate(BaseModel):
    target_type: Literal["experience", "answer", "source"]
    target_id: int
    category: Literal["outdated", "incorrect", "irrelevant_citation", "privacy", "other"]
    description: str = Field(min_length=5, max_length=3000)

class FeedbackHandle(BaseModel):
    status: Literal["maintained", "updated", "disputed", "withdrawn", "needs_more_evidence"]
    handling_note: str = Field(min_length=2, max_length=2000)

class RoleUpdate(BaseModel):
    roles: list[Literal["reader", "contributor", "reviewer", "admin"]]

class ScoreConfigUpdate(BaseModel):
    A: float = Field(ge=0, le=1)
    S: float = Field(ge=0, le=1)
    T: float = Field(ge=0, le=1)
    D: float = Field(ge=0, le=1)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"日期格式无效：{value}") from exc


def _iso(value: datetime | None):
    return value.isoformat() if value else None


def _privacy_warnings(text: str | None) -> list[str]:
    """Conservative first-pass detector; reviewer must still inspect content manually."""
    value = text or ""
    warnings = []
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.IGNORECASE):
        warnings.append("可能包含邮箱地址")
    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
        warnings.append("可能包含中国手机号")
    if re.search(r"(?<!\d)\+\d{1,3}[\s().-]?(?:\d[\s().-]?){7,12}\d(?!\d)", value):
        warnings.append("可能包含国际电话号码")
    return warnings


def _experience_dict(exp: Experience, include_raw: bool = True) -> dict:
    result = {
        "id": exp.id, "course_id": exp.course_id, "course_name": exp.course.name if exp.course else "",
        "school": exp.course.school if exp.course else "", "term": exp.term,
        "author_visibility": exp.author_visibility or "anonymous",
        "original_snapshot_kept": bool(exp.original_raw_text),
        "privacy_warnings": _privacy_warnings(exp.raw_text + " " + " ".join([exp.difficulty or "", exp.assignments or "", exp.assessment or "", exp.advice or ""])),
        "difficulty": exp.difficulty, "assignments": exp.assignments, "assessment": exp.assessment,
        "advice": exp.advice, "status": exp.status, "confirmed": exp.confirmed,
        "ai_mode": exp.ai_mode, "ai_processed_at": _iso(exp.ai_processed_at),
        "review_reason": exp.review_reason, "demo_data": exp.demo_data,
        "created_at": _iso(exp.created_at), "updated_at": _iso(exp.updated_at),
        "submitter_id": exp.submitter_id, "submitter_name": exp.submitter.display_name if exp.submitter else "",
        "source_id": exp.source.id if exp.source else None,
    }
    if include_raw:
        result["raw_text"] = exp.raw_text
    return result


def _record_operation(db: Session, actor_id: int | None, action: str, target_type: str, target_id, result="success", details=None):
    db.add(OperationLog(actor_id=actor_id, action=action, target_type=target_type, target_id=str(target_id), result=result, details=details or {}))


def _make_internal_source(db: Session, exp: Experience, reviewer: User, claim_group: str, unresolved_conflict: bool = False, major_course_change: bool = False) -> SourceRecord:
    existing = db.scalar(select(SourceRecord).where(SourceRecord.experience_id == exp.id))
    if existing:
        existing.status = "active"
        existing.permission = "full_text_allowed"
        existing.link_status = "not_applicable"
        existing.claim_group = claim_group
        existing.unresolved_conflict = unresolved_conflict
        existing.major_course_change = major_course_change
        existing.content_excerpt = exp.raw_text
        existing.term = exp.term
        return existing
    course = exp.course
    source = SourceRecord(
        source_code=f"EXP-{exp.id:04d}", experience_id=exp.id, course_id=course.id,
        title=f"{course.name} · {exp.term} 课程经验（已审核）", author=(exp.submitter.display_name if exp.author_visibility == "display_name" else "匿名贡献者"),
        school=course.school, course_name=course.name, term=exp.term,
        claim_group=claim_group, content_excerpt=exp.raw_text,
        permission="full_text_allowed", status="active", link_status="not_applicable", author_verified=True,
        unresolved_conflict=unresolved_conflict, major_course_change=major_course_change,
        has_concrete_scenario=bool(exp.difficulty and exp.difficulty != "未提及"),
        has_actionable_detail=bool(exp.advice and exp.advice != "未提及"),
        experience_date=exp.created_at, created_by=reviewer.id, demo_data=exp.demo_data,
    )
    db.add(source)
    return source


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.app_env.lower() == "production":
            if settings.seed_demo_data:
                raise RuntimeError("生产环境必须设置 SEED_DEMO_DATA=false，避免初始化演示用户和合成数据。")
            known_weak = {"local-demo-secret-change-before-deploy", "local-compose-key-change-this-before-deploying", "replace-this-secret"}
            placeholder_key = any(part in settings.secret_key.lower() for part in ("replace-this", "change-before-deploy", "local-demo", "local-compose"))
            if len(settings.secret_key) < 32 or settings.secret_key in known_weak or placeholder_key:
                raise RuntimeError("生产环境必须设置至少32字符的随机 SECRET_KEY。")
        Base.metadata.create_all(bind=engine)
        ensure_schema_compatibility()
        if settings.seed_demo_data:
            with SessionLocal() as db:
                seed_database(db)
        yield

    app = FastAPI(title=settings.app_name, version="0.1.0", description="基于校园课程经验的可追溯知识传承原型", lifespan=lifespan)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": settings.app_name, "environment": settings.app_env, "version": app.version}

    @app.get("/api/auth/demo-accounts")
    def demo_accounts():
        # Never expose demo account names as sign-in hints in a production deployment.
        local_only = settings.app_env.lower() != "production"
        accounts = [
            {"username": "reader_demo", "label": "查询者", "roles": ["reader"]},
            {"username": "contributor_demo", "label": "贡献者", "roles": ["reader", "contributor"]},
            {"username": "reviewer_demo", "label": "审核员", "roles": ["reader", "reviewer"]},
            {"username": "admin_demo", "label": "管理员", "roles": ["reader", "admin", "reviewer"]},
        ] if local_only else []
        return {"local_demo_only": local_only, "accounts": accounts}

    @app.post("/api/auth/login")
    def login(body: LoginRequest, db: Session = Depends(get_db)):
        user = db.scalar(select(User).where(User.username == body.username))
        if not user or not user.active or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {"access_token": issue_token(user), "token_type": "bearer", "user": serialize_user(user)}

    @app.get("/api/auth/me")
    def whoami(user: User = Depends(get_current_user)):
        return serialize_user(user)

    @app.get("/api/courses")
    def list_courses(db: Session = Depends(get_db)):
        courses = db.scalars(select(Course).where(Course.active.is_(True)).order_by(Course.name)).all()
        return [{"id": c.id, "school": c.school, "code": c.code, "name": c.name, "default_term": c.default_term} for c in courses]

    @app.get("/api/dashboard")
    def dashboard(db: Session = Depends(get_db)):
        published = db.scalar(select(func.count(Experience.id)).where(Experience.status == "published")) or 0
        review = db.scalar(select(func.count(Experience.id)).where(Experience.status == "pending_review")) or 0
        sources = db.scalar(select(func.count(SourceRecord.id)).where(SourceRecord.status == "active", SourceRecord.permission.in_(list(ALLOWED_RAG_PERMISSIONS)), SourceRecord.duplicate_of_id.is_(None))) or 0
        courses = db.scalar(select(func.count(Course.id)).where(Course.active.is_(True))) or 0
        return {"published_experiences": published, "pending_review": review, "active_sources": sources, "courses": courses,
                "demo_notice": "当前数据库包含合成演示数据；请勿将其描述为真实校内调查结果。"}

    @app.get("/api/search")
    def search(course_id: int | None = None, term: str | None = None, q: str | None = None, limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
        results = search_sources(db, course_id=course_id, term=term, query=q, limit=limit)
        return {"results": results, "count": len(results), "policy": "仅展示已发布且允许公开的记录；仅可展示链接的来源不参与AI生成与评分。"}

    @app.post("/api/experiences")
    async def create_experience(body: ExperienceCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("contributor"))):
        course = db.get(Course, body.course_id)
        if not course or not course.active:
            raise HTTPException(status_code=404, detail="课程不存在或未启用")
        initial_text = body.raw_text.strip()
        exp = Experience(course_id=course.id, submitter_id=user.id, term=body.term.strip(), raw_text=initial_text,
                         original_raw_text=initial_text, author_visibility=body.author_visibility,
                         difficulty="未提及", assignments="未提及", assessment="未提及", advice="未提及", status="draft", confirmed=False)
        db.add(exp); db.commit(); db.refresh(exp)
        # The original text has already been durably saved. Model failure cannot erase it.
        fields, mode = await extract_experience(exp.raw_text, course.name, exp.term)
        exp.difficulty = fields["difficulty"]
        exp.assignments = fields["assignments"]
        exp.assessment = fields["assessment"]
        exp.advice = fields["advice"]
        exp.ai_mode = mode
        exp.ai_processed_at = utcnow()
        db.commit(); db.refresh(exp)
        return {"experience": _experience_dict(exp), "message": "原文已保存。请核对AI整理字段，确认后再送审核。", "saved_original_first": True}

    @app.get("/api/experiences/mine")
    def my_experiences(db: Session = Depends(get_db), user: User = Depends(require_roles("contributor"))):
        rows = db.scalars(select(Experience).options(joinedload(Experience.course), joinedload(Experience.submitter), joinedload(Experience.source)).where(Experience.submitter_id == user.id).order_by(Experience.updated_at.desc())).all()
        return {"results": [_experience_dict(row) for row in rows]}

    @app.get("/api/experiences/{experience_id}")
    def get_experience(experience_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        exp = db.scalar(select(Experience).options(joinedload(Experience.course), joinedload(Experience.submitter), joinedload(Experience.source)).where(Experience.id == experience_id))
        if not exp:
            raise HTTPException(status_code=404, detail="经验记录不存在")
        if exp.submitter_id != user.id and not set(user.roles or []).intersection({"reviewer", "admin"}):
            raise HTTPException(status_code=403, detail="只能查看自己的未发布记录")
        return _experience_dict(exp)

    @app.patch("/api/experiences/{experience_id}")
    async def edit_experience(experience_id: int, body: ExperienceEdit, db: Session = Depends(get_db), user: User = Depends(require_roles("contributor"))):
        exp = db.scalar(select(Experience).options(joinedload(Experience.course), joinedload(Experience.submitter), joinedload(Experience.source)).where(Experience.id == experience_id))
        if not exp:
            raise HTTPException(status_code=404, detail="经验记录不存在")
        if exp.submitter_id != user.id:
            raise HTTPException(status_code=403, detail="只能修改自己的记录")
        if exp.status not in {"draft", "returned"}:
            raise HTTPException(status_code=409, detail="该状态不可编辑；已发布内容需通过纠错流程处理")
        if body.raw_text is not None and body.raw_text.strip() != exp.raw_text:
            if not exp.original_raw_text:
                exp.original_raw_text = exp.raw_text
            exp.raw_text = body.raw_text.strip()
            fields, mode = await extract_experience(exp.raw_text, exp.course.name if exp.course else "", exp.term)
            for key in ("difficulty", "assignments", "assessment", "advice"):
                setattr(exp, key, fields[key])
            exp.ai_mode = mode
            exp.ai_processed_at = utcnow()
        else:
            for key in ("difficulty", "assignments", "assessment", "advice"):
                setattr(exp, key, getattr(body, key).strip() or "未提及")
        exp.updated_at = utcnow()
        db.commit(); db.refresh(exp)
        return {"experience": _experience_dict(exp), "message": "当前文本与结构化字段已保存；首次提交快照保留，不会被覆盖。"}

    @app.post("/api/experiences/{experience_id}/confirm")
    def confirm_experience(experience_id: int, body: ConfirmExperience, db: Session = Depends(get_db), user: User = Depends(require_roles("contributor"))):
        exp = db.scalar(select(Experience).options(joinedload(Experience.course), joinedload(Experience.submitter)).where(Experience.id == experience_id))
        if not exp:
            raise HTTPException(status_code=404, detail="经验记录不存在")
        if exp.submitter_id != user.id:
            raise HTTPException(status_code=403, detail="只能确认自己的记录")
        if exp.status not in {"draft", "returned"}:
            raise HTTPException(status_code=409, detail="当前状态不能重新送审")
        if not body.confirm:
            raise HTTPException(status_code=400, detail="需确认AI整理结果后再送审")
        if body.raw_text is not None and body.raw_text.strip() != exp.raw_text:
            if not exp.original_raw_text:
                exp.original_raw_text = exp.raw_text
            exp.raw_text = body.raw_text.strip()
        for key in ("difficulty", "assignments", "assessment", "advice"):
            setattr(exp, key, getattr(body, key).strip() or "未提及")
        exp.confirmed = True
        exp.status = "pending_review"
        exp.review_reason = ""
        exp.updated_at = utcnow()
        db.commit(); db.refresh(exp)
        return {"experience": _experience_dict(exp), "message": "已送交人工审核；在审核通过前不会公开。"}

    @app.post("/api/experiences/{experience_id}/review")
    def review_experience(experience_id: int, body: ReviewAction, db: Session = Depends(get_db), user: User = Depends(require_roles("reviewer", "admin"))):
        exp = db.scalar(select(Experience).options(joinedload(Experience.course), joinedload(Experience.submitter), joinedload(Experience.source)).where(Experience.id == experience_id))
        if not exp:
            raise HTTPException(status_code=404, detail="经验记录不存在")
        if exp.submitter_id == user.id:
            raise HTTPException(status_code=403, detail="审核员不得审核自己提交的内容")
        if body.action in {"return", "reject", "unpublish"} and not body.reason.strip():
            raise HTTPException(status_code=422, detail="退回、拒绝或下架必须填写理由")
        if body.action in {"approve", "return", "reject"} and exp.status != "pending_review":
            raise HTTPException(status_code=409, detail="只有待审核记录可以执行该动作")
        if body.action == "unpublish" and exp.status != "published":
            raise HTTPException(status_code=409, detail="只有已发布记录可以下架")
        if body.action == "approve":
            if not exp.confirmed:
                raise HTTPException(status_code=409, detail="贡献者尚未确认抽取字段")
            privacy = _privacy_warnings(exp.raw_text + " " + " ".join([exp.difficulty or "", exp.assignments or "", exp.assessment or "", exp.advice or ""]))
            if privacy:
                raise HTTPException(status_code=422, detail="发布前检测到可能的个人信息（" + "、".join(privacy) + "）。请退回或让贡献者修订文本并再次审核。")
            group = body.claim_group.strip()
            if len(group) < 2:
                raise HTTPException(status_code=422, detail="通过发布前，审核员需填写该资料所支持的具体主张/主题组，避免把不同主张混算为独立证据")
            exp.status = "published"
            exp.review_reason = body.reason.strip()
            _make_internal_source(db, exp, user, group, body.unresolved_conflict, body.major_course_change)
        elif body.action == "return":
            exp.status = "returned"; exp.review_reason = body.reason.strip()
            if exp.source:
                exp.source.status = "withdrawn"; exp.source.withdrawal_reason = "退回修改"
        elif body.action == "reject":
            exp.status = "rejected"; exp.review_reason = body.reason.strip()
            if exp.source:
                exp.source.status = "withdrawn"; exp.source.withdrawal_reason = body.reason.strip()
        elif body.action == "unpublish":
            exp.status = "withdrawn"; exp.review_reason = body.reason.strip()
            if exp.source:
                exp.source.status = "withdrawn"; exp.source.withdrawal_reason = body.reason.strip()
        exp.updated_at = utcnow()
        db.add(ReviewLog(reviewer_id=user.id, experience_id=exp.id, action=body.action, reason=body.reason.strip()))
        _record_operation(db, user.id, f"experience.{body.action}", "experience", exp.id, details={"reason": body.reason.strip(), "claim_group": body.claim_group})
        db.commit(); db.refresh(exp)
        return {"experience": _experience_dict(exp), "message": "审核操作已记录；检索仅读取当前有效发布状态。"}

    @app.get("/api/review/queue")
    def review_queue(db: Session = Depends(get_db), user: User = Depends(require_roles("reviewer", "admin"))):
        rows = db.scalars(select(Experience).options(joinedload(Experience.course), joinedload(Experience.submitter)).where(Experience.status == "pending_review").order_by(Experience.created_at.asc())).all()
        return {"results": [_experience_dict(row) for row in rows]}

    @app.post("/api/sources")
    def register_source(body: SourceCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        if body.url and not body.url.lower().startswith(("https://", "http://")):
            raise HTTPException(status_code=422, detail="URL必须是http或https地址")
        parent = None
        if body.duplicate_of_id:
            parent = db.get(SourceRecord, body.duplicate_of_id)
            if not parent:
                raise HTTPException(status_code=404, detail="重复来源指向的原始来源不存在")
            if parent.duplicate_of_id:
                body.duplicate_of_id = parent.duplicate_of_id
                parent = db.get(SourceRecord, body.duplicate_of_id)
        course = db.get(Course, body.course_id) if body.course_id else None
        if body.course_id and not course:
            raise HTTPException(status_code=404, detail="课程不存在")
        if parent:
            new_school = course.school if course else (body.school.strip() or settings.app_school_name)
            new_course = course.name if course else body.course_name.strip()
            if parent.school != new_school or parent.course_name != new_course or parent.claim_group != body.claim_group.strip():
                raise HTTPException(status_code=422, detail="转载归并前必须确认学校、课程与具体主张范围一致；不同范围的资料不能合并计数")
        if body.permission in {"abstract_allowed", "full_text_allowed"} and not body.confirm_reviewed:
            raise HTTPException(status_code=400, detail="请确认已核查出处、作者、适用范围及内容使用许可")
        if body.permission in {"abstract_allowed", "full_text_allowed"} and not body.content_excerpt.strip():
            raise HTTPException(status_code=422, detail="允许摘要/全文用于生成时，必须登记实际获准使用的正文或摘要")
        if body.permission in {"abstract_allowed", "full_text_allowed"} and _privacy_warnings(body.content_excerpt):
            raise HTTPException(status_code=422, detail="登记正文/摘要包含可能的邮箱或手机号；请先脱敏再保存")
        source_code = f"SRC-{uuid4().hex[:8].upper()}"
        status_value = "active" if body.permission in {"link_only", "abstract_allowed", "full_text_allowed"} else ("withdrawn" if body.permission == "prohibited" else "pending")
        source = SourceRecord(
            source_code=source_code, title=body.title.strip(), author=body.author.strip(), organization=body.organization.strip(),
            url=body.url.strip(), link_status=("unchecked" if body.url.strip() else "not_applicable"), source_type=body.source_type, school=(course.school if course else body.school.strip() or settings.app_school_name),
            course_id=body.course_id, course_name=(course.name if course else body.course_name.strip()), term=body.term.strip(),
            claim_group=body.claim_group.strip(), content_excerpt=(body.content_excerpt.strip() if body.permission in {"abstract_allowed", "full_text_allowed"} else ""), permission=body.permission,
            status=status_value, duplicate_of_id=body.duplicate_of_id, author_verified=body.author_verified,
            official=body.official, current_official_fact=body.current_official_fact, major_course_change=body.major_course_change, unresolved_conflict=body.unresolved_conflict,
            has_concrete_scenario=body.has_concrete_scenario, has_actionable_detail=body.has_actionable_detail,
            experience_date=_parse_date(body.experience_date), published_at=_parse_date(body.published_at), obtained_at=_parse_date(body.obtained_at) or utcnow(),
            created_by=user.id, demo_data=False)
        db.add(source); db.flush()
        _record_operation(db, user.id, "source.register", "source", source.id, details={"permission": source.permission, "status": source.status, "duplicate_of_id": source.duplicate_of_id})
        db.commit(); db.refresh(source)
        return {"source": source_dict(db, source), "message": "来源已登记。仅允许范围内的内容可进入AI上下文；仅链接条目不参与评分。"}

    @app.get("/api/sources")
    def list_sources(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        if not set(user.roles or []).intersection({"admin", "reviewer"}):
            # Public users only receive permitted active sources, never internal review details.
            sources = db.scalars(select(SourceRecord).options(joinedload(SourceRecord.experience), joinedload(SourceRecord.duplicate_of)).where(SourceRecord.status == "active", SourceRecord.permission.in_(list(VISIBLE_PERMISSIONS))).order_by(SourceRecord.created_at.desc())).all()
            sources = [item for item in sources if not (item.url and item.link_status == "invalid")]
        else:
            sources = db.scalars(select(SourceRecord).options(joinedload(SourceRecord.experience), joinedload(SourceRecord.duplicate_of)).order_by(SourceRecord.created_at.desc())).all()
        return {"results": [source_dict(db, item) for item in sources]}

    @app.get("/api/sources/{source_id}")
    def get_source_detail(source_id: int, db: Session = Depends(get_db)):
        source = db.scalar(select(SourceRecord).options(joinedload(SourceRecord.experience), joinedload(SourceRecord.duplicate_of)).where(SourceRecord.id == source_id))
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")
        if source.status != "active" or source.permission not in VISIBLE_PERMISSIONS or (source.url and source.link_status == "invalid"):
            raise HTTPException(status_code=404, detail="来源当前不可公开访问或其外部链接已失效")
        if source.duplicate_of_id is not None:
            raise HTTPException(status_code=404, detail="该转载已归并，请查看原始来源")
        if source.experience_id is not None and (not source.experience or source.experience.status != "published"):
            raise HTTPException(status_code=404, detail="关联经验当前未公开")
        return source_dict(db, source)

    @app.put("/api/sources/{source_id}/permission")
    def update_source_permission(source_id: int, body: PermissionUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        source = db.get(SourceRecord, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")
        old = source.permission
        if body.permission in {"abstract_allowed", "full_text_allowed"}:
            if not body.confirm_reviewed:
                raise HTTPException(status_code=400, detail="请确认已重新核查出处、作者、适用范围与使用许可")
            new_excerpt = (body.content_excerpt or source.content_excerpt or "").strip()
            if not new_excerpt:
                raise HTTPException(status_code=422, detail="此来源没有已获准保存的正文/摘要，请先补充获准内容")
            if _privacy_warnings(new_excerpt):
                raise HTTPException(status_code=422, detail="正文/摘要包含可能的邮箱或手机号；请先脱敏再保存")
            source.content_excerpt = new_excerpt
        else:
            # When the new permission does not allow text processing, do not retain copied source content.
            source.content_excerpt = ""
        source.permission = body.permission
        if body.permission in {"pending", "prohibited"}:
            source.status = "withdrawn" if body.permission == "prohibited" else "pending"
            source.withdrawal_reason = body.reason.strip()
        else:
            source.status = "active"
            source.withdrawal_reason = ""
        db.add(OperationLog(actor_id=user.id, action="source.permission.update", target_type="source", target_id=str(source.id), result="success", details={"old_permission": old, "new_permission": body.permission, "reason": body.reason.strip()}))
        db.commit(); db.refresh(source)
        return {"source": source_dict(db, source), "message": "权限状态已更新；后续检索会即时应用当前权限和状态过滤。"}

    @app.put("/api/sources/{source_id}/link-status")
    def update_source_link_status(source_id: int, body: LinkStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        source = db.get(SourceRecord, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")
        if not source.url.strip():
            raise HTTPException(status_code=409, detail="该记录使用平台内部稳定ID，无外部链接需要核验")
        old_status = source.link_status
        source.link_status = body.link_status
        source.link_checked_at = utcnow()
        if body.link_status == "invalid":
            source.withdrawal_reason = body.reason.strip()
        _record_operation(db, user.id, "source.link_status.update", "source", source.id,
                          details={"old_status": old_status, "new_status": body.link_status, "reason": body.reason.strip()})
        db.commit(); db.refresh(source)
        return {"source": source_dict(db, source), "message": ("链接已标记失效，已从公开搜索和AI问答中排除。" if body.link_status == "invalid" else "链接状态已更新；请保存人工核验依据。")}

    @app.get("/api/credibility")
    def credibility(course_id: int | None = None, db: Session = Depends(get_db)):
        course_school = None
        if course_id:
            course = db.get(Course, course_id)
            course_school = course.school if course else None
        stmt = select(SourceRecord).options(joinedload(SourceRecord.duplicate_of), joinedload(SourceRecord.experience)).where(
            SourceRecord.status == "active", SourceRecord.permission.in_(list(VISIBLE_PERMISSIONS)))
        if course_id:
            stmt = stmt.where(SourceRecord.course_id == course_id)
        rows = db.scalars(stmt).all()
        rows = [item for item in rows if not (item.url and item.link_status == "invalid")]
        # 跨校资料不能作为本校课程事实证据：来源学校必须与所选课程学校一致。
        if course_id and course_school:
            rows = [item for item in rows if bool(item.school) and item.school == course_school]
        scored = score_sources(db, rows)
        return {"results": scored, "weights": get_score_config(db)[0], "rule_version": get_score_config(db)[1],
                "formula": "C = 0.40 × A + 0.25 × S + 0.20 × T + 0.15 × D（默认V1.0权重）",
                "note": "分数用于提示证据质量，不是事实为真的概率。转载不计为独立来源；‘最可信参考’是当前候选内的相对排序。"}

    @app.post("/api/qa")
    async def ask_question(body: QuestionRequest, db: Session = Depends(get_db)):
        course = db.get(Course, body.course_id) if body.course_id else None
        evidence = await retrieve_evidence(db, body.question, course_id=body.course_id, term=body.term)
        answer_text, model_mode, used_ids = await answer_from_evidence(body.question, evidence)
        answer = AnswerRecord(question=body.question.strip(), answer_text=answer_text,
                              sufficiency=("insufficient" if not evidence else "conflict" if any(item.get("unresolved_conflict") for item in evidence) else "limited" if len(evidence) == 1 else "supported"),
                              note="; ".join(sorted({item.get("scope_note", "") for item in evidence if item.get("scope_note")})), model_mode=model_mode)
        db.add(answer); db.flush()
        used = [item for item in evidence if item["id"] in used_ids]
        weights, version = get_score_config(db)
        for item in used:
            source = db.get(SourceRecord, item["id"])
            score_date = (source.score_reference_date or utcnow()) if source else utcnow()
            score = score_source(db, source, weights, version, now=score_date) if source else {}
            db.add(EvidenceLink(answer_id=answer.id, source_id=item["id"], claim=body.question,
                                stance="supports", relevance_score=item.get("relevance", 0), score_a=score.get("score_a"),
                                score_s=score.get("score_s"), score_t=score.get("score_t"), score_d=score.get("score_d"),
                                credibility_score=score.get("score"), credibility_grade=score.get("grade", "暂不评分"), rule_version=version,
                                score_reference_date=score_date))
        db.commit(); db.refresh(answer)
        citations = []
        for item in used:
            citations.append({"id": item["id"], "source_code": item["source_code"], "title": item["title"], "author": item.get("author"),
                              "source_type": item["source_type"], "url": item.get("url"), "course_name": item.get("course_name"), "term": item.get("term"),
                              "score": item.get("score"), "grade": item.get("grade"), "most_credible": item.get("most_credible"),
                              "score_a": item.get("score_a"), "score_s": item.get("score_s"), "score_t": item.get("score_t"), "score_d": item.get("score_d"),
                              "limitations": item.get("limitations", []), "scope_note": item.get("scope_note", ""), "demo_data": item.get("demo_data", False)})
        if not citations:
            answer_text = "暂未找到足够的已审核且获准使用的证据。系统未生成无来源结论。请尝试补充课程、学期或更具体的关键词。"
        conflicts = any(item.get("unresolved_conflict") for item in evidence)
        return {"answer_id": answer.id, "question": body.question, "answer": answer_text, "sufficiency": answer.sufficiency,
                "model_mode": model_mode, "citations": citations,
                "notice": "可信度分数是证据质量提示，不是事实为真的概率。" + ("存在冲突，需并列核对来源。" if conflicts else ""),
                "demo_warning": "部分候选为合成演示数据。" if any(item.get("demo_data") for item in citations) else ""}

    @app.get("/api/answers/{answer_id}")
    def answer_detail(answer_id: int, db: Session = Depends(get_db)):
        answer = db.get(AnswerRecord, answer_id)
        if not answer:
            raise HTTPException(status_code=404, detail="回答记录不存在")
        links = db.scalars(select(EvidenceLink).options(joinedload(EvidenceLink.source)).where(EvidenceLink.answer_id == answer_id)).all()
        return {"id": answer.id, "question": answer.question, "answer": answer.answer_text, "sufficiency": answer.sufficiency,
                "created_at": _iso(answer.created_at), "citations": [{"source_id": link.source_id, "source_code": link.source.source_code, "title": link.source.title,
                "claim": link.claim, "stance": link.stance, "relevance_score": link.relevance_score, "credibility_score": link.credibility_score,
                "credibility_grade": link.credibility_grade, "rule_version": link.rule_version,
                "score_reference_date": _iso(link.score_reference_date)} for link in links]}

    @app.post("/api/feedback")
    def submit_feedback(body: FeedbackCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        target_model = {"experience": Experience, "answer": AnswerRecord, "source": SourceRecord}[body.target_type]
        if not db.get(target_model, body.target_id):
            raise HTTPException(status_code=404, detail="反馈目标不存在")
        code = f"FB-{uuid4().hex[:8].upper()}"
        item = Feedback(feedback_code=code, user_id=user.id, target_type=body.target_type, target_id=body.target_id,
                        category=body.category, description=body.description.strip(), status="pending")
        db.add(item); db.commit(); db.refresh(item)
        return {"feedback_id": item.id, "feedback_code": item.feedback_code, "status": item.status,
                "message": "反馈已记录；审核确认前不会直接改写知识库。此功能属于P1。"}

    @app.get("/api/feedback")
    def list_feedback(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
        if set(user.roles or []).intersection({"reviewer", "admin"}):
            rows = db.scalars(select(Feedback).order_by(Feedback.created_at.desc())).all()
        else:
            rows = db.scalars(select(Feedback).where(Feedback.user_id == user.id).order_by(Feedback.created_at.desc())).all()
        return {"results": [{"id": f.id, "feedback_code": f.feedback_code, "target_type": f.target_type, "target_id": f.target_id,
                             "category": f.category, "description": f.description, "status": f.status,
                             "handling_note": f.handling_note, "created_at": _iso(f.created_at)} for f in rows]}

    @app.patch("/api/feedback/{feedback_id}")
    def handle_feedback(feedback_id: int, body: FeedbackHandle, db: Session = Depends(get_db), user: User = Depends(require_roles("reviewer", "admin"))):
        feedback = db.get(Feedback, feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈记录不存在")
        feedback.status = body.status; feedback.handling_note = body.handling_note.strip(); feedback.handled_by = user.id; feedback.handled_at = utcnow()
        if feedback.target_type == "experience":
            db.add(ReviewLog(reviewer_id=user.id, experience_id=feedback.target_id, action=f"feedback.{body.status}", reason=body.handling_note.strip()))
        _record_operation(db, user.id, "feedback.handle", "feedback", feedback.id, details={"status": body.status, "note": body.handling_note.strip()})
        db.commit()
        return {"id": feedback.id, "status": feedback.status, "handling_note": feedback.handling_note}

    @app.get("/api/admin/users")
    def list_users(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        users = db.scalars(select(User).order_by(User.id)).all()
        return {"results": [serialize_user(item) for item in users]}

    @app.patch("/api/admin/users/{target_user_id}/roles")
    def update_roles(target_user_id: int, body: RoleUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        target = db.get(User, target_user_id)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not body.roles:
            raise HTTPException(status_code=422, detail="用户至少需要一个角色")
        old = target.roles; target.roles = sorted(set(body.roles))
        _record_operation(db, user.id, "user.roles.update", "user", target.id, details={"old_roles": old, "new_roles": target.roles})
        db.commit(); db.refresh(target)
        return serialize_user(target)

    @app.get("/api/admin/scoring-config")
    def read_score_config(version: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        weights, rule_version = get_score_config(db, version)
        return {"weights": weights, "version": rule_version, "formula": "C = A×wA + S×wS + T×wT + D×wD"}

    @app.put("/api/admin/scoring-config")
    def update_score_config(body: ScoreConfigUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        weights = {"A": body.A, "S": body.S, "T": body.T, "D": body.D}
        if abs(sum(weights.values()) - 1.0) > 0.0001:
            raise HTTPException(status_code=422, detail="A/S/T/D权重之和必须为1.0")
        setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "score_weights"))
        old = setting.value if setting else DEFAULT_WEIGHTS
        version_num = 2
        if setting:
            old_version = setting.version or "V1.0"
            archive_key = f"score_weights_{old_version}"
            if not db.scalar(select(SystemSetting).where(SystemSetting.key == archive_key)):
                db.add(SystemSetting(key=archive_key, value=dict(old), version=old_version, updated_by=user.id))
            match = re.match(r"V(\d+)", old_version)
            version_num = (int(match.group(1)) + 1) if match else 2
            setting.value = weights; setting.version = f"V{version_num}.0"; setting.updated_by = user.id; setting.updated_at = utcnow()
        else:
            setting = SystemSetting(key="score_weights", value=weights, version="V2.0", updated_by=user.id)
            db.add(setting)
        _record_operation(db, user.id, "scoring_config.update", "system_setting", "score_weights", details={"old_weights": old, "new_weights": weights, "new_version": setting.version})
        db.commit()
        return {"weights": weights, "version": setting.version, "message": "评分规则已更新；相同证据在同一规则版本下可复算。请在验收报告中记录规则版本。"}

    @app.get("/api/admin/logs")
    def list_operation_logs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        rows = db.scalars(select(OperationLog).order_by(OperationLog.created_at.desc()).limit(limit)).all()
        review_rows = db.scalars(select(ReviewLog).order_by(ReviewLog.created_at.desc()).limit(limit)).all()
        return {"operation_logs": [{"id": x.id, "actor_id": x.actor_id, "action": x.action, "target_type": x.target_type, "target_id": x.target_id, "result": x.result, "details": x.details, "created_at": _iso(x.created_at)} for x in rows],
                "review_logs": [{"id": x.id, "reviewer_id": x.reviewer_id, "experience_id": x.experience_id, "action": x.action, "reason": x.reason, "created_at": _iso(x.created_at)} for x in review_rows]}

    @app.get("/api/admin/maintenance/candidates")
    def maintenance_candidates(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
        # P1: suggest only. Never merge, overwrite, or delete without a human decision.
        rows = db.scalars(select(SourceRecord).options(joinedload(SourceRecord.experience)).where(SourceRecord.status == "active", SourceRecord.duplicate_of_id.is_(None))).all()
        candidates = []
        from .services.retrieval import tokenize
        for i, left in enumerate(rows):
            left_text = (left.title + " " + left.content_excerpt).lower()
            left_tokens = tokenize(left_text)
            date = left.experience_date or left.published_at
            if date and (utcnow() - date).days >= 730:
                candidates.append({"type": "expiry_review", "source_id": left.id, "source_code": left.source_code, "title": left.title,
                                  "reason": "资料距今已约两年或更久，建议人工核查适用性；系统不会自动下架。"})
            for right in rows[i+1:]:
                if left.course_name != right.course_name or left.school != right.school:
                    continue
                right_text = (right.title + " " + right.content_excerpt).lower()
                right_tokens = tokenize(right_text)
                union = left_tokens | right_tokens
                similarity = len(left_tokens & right_tokens) / len(union) if union else 0
                if similarity >= 0.55:
                    candidates.append({"type": "possible_duplicate", "source_id": left.id, "source_code": left.source_code,
                                       "other_source_id": right.id, "other_source_code": right.source_code, "similarity": round(similarity, 2),
                                       "reason": "仅为近似重复候选，请人工比较原文、出处及独立性。"})
        return {"results": candidates[:200], "note": "P1维护建议：无自动合并、覆盖、删除行为。"}

    @app.get("/api/admin/metrics")
    def anonymized_metrics(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
        # P2: aggregated counts only, no personal identifiers or per-user ranking.
        return {"published_experiences": db.scalar(select(func.count(Experience.id)).where(Experience.status == "published")) or 0,
                "pending_review": db.scalar(select(func.count(Experience.id)).where(Experience.status == "pending_review")) or 0,
                "feedback_total": db.scalar(select(func.count(Feedback.id)) ) or 0,
                "feedback_pending": db.scalar(select(func.count(Feedback.id)).where(Feedback.status == "pending")) or 0,
                "active_permitted_sources": db.scalar(select(func.count(SourceRecord.id)).where(SourceRecord.status == "active", SourceRecord.permission.in_(list(ALLOWED_RAG_PERMISSIONS)), SourceRecord.duplicate_of_id.is_(None))) or 0,
                "privacy_note": "仅聚合统计，不返回个人敏感信息；此视图属于P2扩展。"}

    return app

app = create_app()
