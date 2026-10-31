from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(256))
    roles: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    experiences: Mapped[list["Experience"]] = relationship(back_populates="submitter")

class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school: Mapped[str] = mapped_column(String(160), index=True)
    code: Mapped[str] = mapped_column(String(40), default="")
    name: Mapped[str] = mapped_column(String(160), index=True)
    default_term: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    experiences: Mapped[list["Experience"]] = relationship(back_populates="course")

class Experience(Base):
    __tablename__ = "experiences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    submitter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    term: Mapped[str] = mapped_column(String(80), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    original_raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    author_visibility: Mapped[str] = mapped_column(String(40), default="anonymous", nullable=False)
    difficulty: Mapped[str] = mapped_column(Text, default="未提及")
    assignments: Mapped[str] = mapped_column(Text, default="未提及")
    assessment: Mapped[str] = mapped_column(Text, default="未提及")
    advice: Mapped[str] = mapped_column(Text, default="未提及")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_mode: Mapped[str] = mapped_column(String(40), default="rule-fallback")
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_reason: Mapped[str] = mapped_column(Text, default="")
    demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    course: Mapped[Course] = relationship(back_populates="experiences")
    submitter: Mapped[User] = relationship(back_populates="experiences")
    source: Mapped["SourceRecord | None"] = relationship(back_populates="experience", uselist=False)

class SourceRecord(Base):
    __tablename__ = "source_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, default="")
    experience_id: Mapped[int | None] = mapped_column(ForeignKey("experiences.id"), nullable=True, unique=True, index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    author: Mapped[str] = mapped_column(String(200), default="")
    organization: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    link_status: Mapped[str] = mapped_column(String(40), default="unchecked", index=True)
    link_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(60), default="student_experience")
    school: Mapped[str] = mapped_column(String(160), default="")
    course_name: Mapped[str] = mapped_column(String(160), default="", index=True)
    term: Mapped[str] = mapped_column(String(80), default="")
    claim_group: Mapped[str] = mapped_column(String(180), default="general_course_experience", index=True)
    content_excerpt: Mapped[str] = mapped_column(Text, default="")
    permission: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("source_records.id"), nullable=True, index=True)
    author_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    official: Mapped[bool] = mapped_column(Boolean, default=False)
    current_official_fact: Mapped[bool] = mapped_column(Boolean, default=False)
    major_course_change: Mapped[bool] = mapped_column(Boolean, default=False)
    unresolved_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    has_concrete_scenario: Mapped[bool] = mapped_column(Boolean, default=False)
    has_actionable_detail: Mapped[bool] = mapped_column(Boolean, default=False)
    experience_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    obtained_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score_reference_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    demo_data: Mapped[bool] = mapped_column(Boolean, default=False)
    withdrawal_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    experience: Mapped[Experience | None] = relationship(back_populates="source", foreign_keys=[experience_id])
    course: Mapped[Course | None] = relationship()
    duplicate_of: Mapped["SourceRecord | None"] = relationship(remote_side=[id], foreign_keys=[duplicate_of_id])

class AnswerRecord(Base):
    __tablename__ = "answer_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    sufficiency: Mapped[str] = mapped_column(String(40), default="unknown")
    note: Mapped[str] = mapped_column(Text, default="")
    model_mode: Mapped[str] = mapped_column(String(60), default="evidence-template")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    evidence: Mapped[list["EvidenceLink"]] = relationship(back_populates="answer", cascade="all, delete-orphan")

class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("answer_records.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), index=True)
    claim: Mapped[str] = mapped_column(Text, default="")
    stance: Mapped[str] = mapped_column(String(40), default="supports")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_t: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    credibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    credibility_grade: Mapped[str] = mapped_column(String(40), default="暂不评分")
    rule_version: Mapped[str] = mapped_column(String(40), default="V1.0")
    score_reference_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    answer: Mapped[AnswerRecord] = relationship(back_populates="evidence")
    source: Mapped[SourceRecord] = relationship()

class ReviewLog(Base):
    __tablename__ = "review_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    experience_id: Mapped[int] = mapped_column(ForeignKey("experiences.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    handling_note: Mapped[str] = mapped_column(Text, default="")
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class OperationLog(Base):
    __tablename__ = "operation_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(80), default="")
    result: Mapped[str] = mapped_column(String(40), default="success")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[str] = mapped_column(String(40), default="V1.0")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
