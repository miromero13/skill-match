import uuid
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base, TimestampMixin
from app.core.catalog_names import catalog_name_key


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("parent_id", "normalized_name", name="uq_categories_parent_name"),
        Index("uq_categories_root_name", "normalized_name", unique=True, postgresql_where=text("parent_id IS NULL")),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_categories_not_self_parent"),
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True)
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)

    @validates("name")
    def normalize_name(self, key, value):
        self.normalized_name = catalog_name_key(value)
        return " ".join(value.split())

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    skills: Mapped[list["Skill"]] = relationship(back_populates="category")


class ChallengeType(Base, TimestampMixin):
    __tablename__ = "challenge_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    evaluation_modality: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    skills: Mapped[list["Skill"]] = relationship(back_populates="challenge_type")


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("category_id", "normalized_name", name="uq_skills_category_name"),)

    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)

    @validates("name")
    def normalize_name(self, key, value):
        self.normalized_name = catalog_name_key(value)
        return " ".join(value.split())

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    challenge_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("challenge_types.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(170), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    min_approval_threshold: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    is_ready_to_publish: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category: Mapped[Category] = relationship(back_populates="skills")
    challenge_type: Mapped[Optional[ChallengeType]] = relationship(back_populates="skills")
    levels: Mapped[list["SkillLevel"]] = relationship(back_populates="skill", cascade="all, delete-orphan", order_by="SkillLevel.level_number")


class SkillLevel(Base, TimestampMixin):
    __tablename__ = "skill_levels"
    __table_args__ = (UniqueConstraint("skill_id", "level_number", name="uq_skill_levels_skill_level"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    skill: Mapped[Skill] = relationship(back_populates="levels")
    rubric: Mapped[Optional["Rubric"]] = relationship(back_populates="skill_level", uselist=False, cascade="all, delete-orphan")


class Rubric(Base, TimestampMixin):
    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_levels.id", ondelete="CASCADE"), unique=True, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    min_score: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    criteria: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    skill_level: Mapped[SkillLevel] = relationship(back_populates="rubric")
