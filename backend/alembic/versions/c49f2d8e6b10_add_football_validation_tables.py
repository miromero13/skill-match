"""add football validation tables

Revision ID: c49f2d8e6b10
Revises: b28e1c5f3a71
Create Date: 2026-11-15 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c49f2d8e6b10"
down_revision: Union[str, Sequence[str], None] = "b28e1c5f3a71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend dataset_samples with football labeling and split columns
    op.add_column(
        "dataset_samples",
        sa.Column("participant_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "dataset_samples",
        sa.Column("level_label", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "dataset_samples",
        sa.Column("manual_touch_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "dataset_samples",
        sa.Column("noise_level", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "dataset_samples",
        sa.Column("surface", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "dataset_samples",
        sa.Column("split", sa.String(length=20), nullable=True),
    )
    op.create_index(
        op.f("ix_dataset_samples_participant_id"),
        "dataset_samples",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dataset_samples_split"),
        "dataset_samples",
        ["split"],
        unique=False,
    )

    # 2. validation_sessions
    op.create_table(
        "validation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("semilla", sa.Integer(), nullable=False),
        sa.Column("plan_firmado", sa.Text(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_modelo", sa.String(length=64), nullable=False),
        sa.Column("version_config", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_validation_sessions_estado"),
        "validation_sessions",
        ["estado"],
        unique=False,
    )
    op.create_index(
        op.f("ix_validation_sessions_skill_id"),
        "validation_sessions",
        ["skill_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_validation_sessions_user_id"),
        "validation_sessions",
        ["user_id"],
        unique=False,
    )

    # 3. challenge_segments
    op.create_table(
        "challenge_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("indice", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("inicio_servidor_ms", sa.Integer(), nullable=False),
        sa.Column("duracion_ms", sa.Integer(), nullable=False),
        sa.Column("cumplimiento", sa.Float(), nullable=True),
        sa.Column("latencia_reaccion_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["validation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_challenge_segments_session_id"),
        "challenge_segments",
        ["session_id"],
        unique=False,
    )

    # 4. evidence_files
    op.create_table(
        "evidence_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("ruta_minio", sa.String(length=500), nullable=False),
        sa.Column("duracion_s", sa.Float(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["validation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_files_session_id"),
        "evidence_files",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_files_sha256"),
        "evidence_files",
        ["sha256"],
        unique=False,
    )

    # 5. detected_events
    op.create_table(
        "detected_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("t_ms", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("confianza", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["validation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_detected_events_session_id"),
        "detected_events",
        ["session_id"],
        unique=False,
    )

    # 6. session_features
    op.create_table(
        "session_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["validation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_session_features_session_id"),
        "session_features",
        ["session_id"],
        unique=True,
    )

    # 7. validation_results
    op.create_table(
        "validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nivel", sa.String(length=40), nullable=False),
        sa.Column("probabilidades", sa.JSON(), nullable=False),
        sa.Column("confianza", sa.Float(), nullable=False),
        sa.Column("puntaje_riesgo", sa.Float(), nullable=False),
        sa.Column("requiere_revision", sa.Boolean(), nullable=False),
        sa.Column("retroalimentacion", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["validation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_validation_results_session_id"),
        "validation_results",
        ["session_id"],
        unique=True,
    )

    # 8. fraud_incidents
    op.create_table(
        "fraud_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("severidad", sa.String(length=20), nullable=False),
        sa.Column("t_ms", sa.Integer(), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["validation_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fraud_incidents_session_id"),
        "fraud_incidents",
        ["session_id"],
        unique=False,
    )

    # 9. model_versions
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("ruta_onnx", sa.String(length=500), nullable=False),
        sa.Column("metricas", sa.JSON(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_versions_nombre"),
        "model_versions",
        ["nombre"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_model_versions_nombre"), table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index(op.f("ix_fraud_incidents_session_id"), table_name="fraud_incidents")
    op.drop_table("fraud_incidents")

    op.drop_index(
        op.f("ix_validation_results_session_id"), table_name="validation_results"
    )
    op.drop_table("validation_results")

    op.drop_index(
        op.f("ix_session_features_session_id"), table_name="session_features"
    )
    op.drop_table("session_features")

    op.drop_index(op.f("ix_detected_events_session_id"), table_name="detected_events")
    op.drop_table("detected_events")

    op.drop_index(op.f("ix_evidence_files_sha256"), table_name="evidence_files")
    op.drop_index(op.f("ix_evidence_files_session_id"), table_name="evidence_files")
    op.drop_table("evidence_files")

    op.drop_index(
        op.f("ix_challenge_segments_session_id"), table_name="challenge_segments"
    )
    op.drop_table("challenge_segments")

    op.drop_index(
        op.f("ix_validation_sessions_user_id"), table_name="validation_sessions"
    )
    op.drop_index(
        op.f("ix_validation_sessions_skill_id"), table_name="validation_sessions"
    )
    op.drop_index(
        op.f("ix_validation_sessions_estado"), table_name="validation_sessions"
    )
    op.drop_table("validation_sessions")

    op.drop_index(op.f("ix_dataset_samples_split"), table_name="dataset_samples")
    op.drop_index(
        op.f("ix_dataset_samples_participant_id"), table_name="dataset_samples"
    )
    op.drop_column("dataset_samples", "split")
    op.drop_column("dataset_samples", "surface")
    op.drop_column("dataset_samples", "noise_level")
    op.drop_column("dataset_samples", "manual_touch_count")
    op.drop_column("dataset_samples", "level_label")
    op.drop_column("dataset_samples", "participant_id")
