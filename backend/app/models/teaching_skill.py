
import uuid 
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column 
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin

class TeachingSkill(Base, TimestampMixin):
    __tablename__ = "user_teaching_skills"
    __tableargs__ = (
        UniqueConstraint(
            "user_id", "skill_id", 
            name = "uq_teaching_user_skill", 
        ),
        CheckConstraint(
            "years_of_experience BETWEEN 0 AND 60 ",
            name = "uq_teaching_experience", 
        ),
        CheckConstraint(
            "declared_level IN "
            "('BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'EXPERT')",
            name="ck_teaching_level",
        ),
        CheckConstraint(
            "(accepts_points = true AND hourly_points_rate > 0 "
            "AND hourly_points_rate IS NOT NULL) OR "
            "(accepts_points = false AND hourly_points_rate IS NULL)",
            name="ck_teaching_rate",
        ),
    )
    id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid = True), primary_key = True , default = uuid.uuid4,
    )
    user_id : Mapped[uuid.UUID]= mapped_column(
        ForeignKey("users.id", ondelete= "CASCADE"), nullable = False,
    )
    skill_id : Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable = False , index = True 
    )
    declared_level :Mapped[str] = mapped_column(String(20),  nullable = False)  #nivel declarado 
    years_of_experence  : Mapped[int] = mapped_column(Integer, nullable = False)    # años de experiencia
    description: Mapped[str | None] = mapped_column(String(2000)) # descripcion
    accepts_points: Mapped[bool] = mapped_column(nullable = False, default = False) # puntos 
    hourly_points_rate: Mapped[int | None] =  mapped_column(Integer) #tarifa por puntos 
    status :Mapped[str]  = mapped_column(
        String(20), nullable = False, default = "DECLARADA"
    )
