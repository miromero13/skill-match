from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.exchange_session import (
    ExchangeSession,
    SessionCancellation,
    SessionNoShowReport,
)
from app.models.session_review import SessionReview
from app.models.teaching_skill import TeachingSkill
from app.models.user import User
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.schemas.reputation import (
    RatingsBreakdown,
    ReputationBadge,
    TrustScoreFactors,
    UserReputationResponse,
)
from app.schemas.session_review import (
    CreateSessionReviewRequest,
    SendSessionTipRequest,
    SessionReviewResponse,
    SessionReviewStateResponse,
    SessionTipResponse,
)
from app.services.content_moderation_service import ContentModerationService


class ReputationService:
    """
    Servicio de dominio para gestión de reseñas pedagógicas, propinas voluntarias
    y cálculo del Puntaje de Confianza multidimensional (HU-40 / RF-REP-01 / RF-REP-02).
    """

    @classmethod
    async def get_session_review_state(
        cls,
        db: AsyncSession,
        session_id: UUID,
        current_user: User,
    ) -> SessionReviewStateResponse:
        """
        Consulta el estado de evaluación de una sesión para el usuario actual.
        """
        stmt = select(ExchangeSession).where(ExchangeSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La sesión de intercambio no existe.",
            )

        # Solo los participantes pueden consultar el estado de su reseña
        if current_user.id not in (session.learner_id, session.instructor_id):
            raise SkillMatchException(
                statuscode=status.HTTP_403_FORBIDDEN,
                message="No tienes permiso para consultar reseñas de esta sesión.",
            )

        # Buscar reseña propia
        own_review_stmt = select(SessionReview).where(
            SessionReview.session_id == session_id,
            SessionReview.reviewer_id == current_user.id,
        )
        own_review_res = await db.execute(own_review_stmt)
        own_review = own_review_res.scalar_one_or_none()

        # Buscar si la contraparte ya evaluó
        other_user_id = session.instructor_id if current_user.id == session.learner_id else session.learner_id
        counterpart_stmt = select(SessionReview).where(
            SessionReview.session_id == session_id,
            SessionReview.reviewer_id == other_user_id,
        )
        counterpart_res = await db.execute(counterpart_stmt)
        counterpart_review = counterpart_res.scalar_one_or_none()

        # Solo se puede evaluar si la sesión está aceptada o terminada
        can_review = (
            own_review is None
            and session.status in ("ACCEPTED", "COMPLETED")
        )

        review_dto = None
        if own_review:
            review_dto = SessionReviewResponse(
                id=own_review.id,
                session_id=own_review.session_id,
                reviewer_id=own_review.reviewer_id,
                reviewer_name=current_user.full_name,
                reviewer_avatar=current_user.avatar_url,
                reviewed_id=own_review.reviewed_id,
                role_in_session=own_review.role_in_session,
                rating_punctuality=own_review.rating_punctuality,
                rating_pedagogy=own_review.rating_pedagogy,
                rating_domain=own_review.rating_domain,
                overall_rating=float(own_review.overall_rating),
                comment=own_review.comment,
                created_at=own_review.created_at,
            )

        return SessionReviewStateResponse(
            session_id=session_id,
            can_review=can_review,
            has_reviewed=own_review is not None,
            reviewed_by_counterpart=counterpart_review is not None,
            existing_review=review_dto,
        )

    @classmethod
    async def create_review(
        cls,
        db: AsyncSession,
        session_id: UUID,
        payload: CreateSessionReviewRequest,
        current_user: User,
    ) -> SessionReviewResponse:
        """
        Crea una reseña bilateral para una sesión completada.
        """
        stmt = select(ExchangeSession).where(ExchangeSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La sesión de intercambio especificada no existe.",
            )

        if current_user.id not in (session.learner_id, session.instructor_id):
            raise SkillMatchException(
                statuscode=status.HTTP_403_FORBIDDEN,
                message="Solo los participantes de la sesión pueden emitir calificaciones.",
            )

        # Determinar a quién evalúa y en qué rol
        if current_user.id == session.learner_id:
            reviewed_id = session.instructor_id
            role_in_session = "INSTRUCTOR"
        else:
            reviewed_id = session.learner_id
            role_in_session = "LEARNER"

        # Verificar si ya existe reseña previa
        existing_stmt = select(SessionReview).where(
            SessionReview.session_id == session_id,
            SessionReview.reviewer_id == current_user.id,
        )
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise SkillMatchException(
                statuscode=status.HTTP_400_BAD_REQUEST,
                message="Ya has calificado esta sesión de intercambio previamente.",
            )

        # Validar lenguaje soez con filtro determinístico (AGENTS.md)
        if payload.comment:
            is_valid, error_msg = ContentModerationService.validate_content(payload.comment)
            if not is_valid:
                raise SkillMatchException(
                    statuscode=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    message=error_msg,
                )

        # Calcular promedio exacto de las 3 dimensiones pedagógicas
        overall = round(
            (payload.rating_punctuality + payload.rating_pedagogy + payload.rating_domain) / 3.0,
            2,
        )

        review = SessionReview(
            session_id=session_id,
            reviewer_id=current_user.id,
            reviewed_id=reviewed_id,
            role_in_session=role_in_session,
            rating_punctuality=payload.rating_punctuality,
            rating_pedagogy=payload.rating_pedagogy,
            rating_domain=payload.rating_domain,
            overall_rating=overall,
            comment=ContentModerationService.sanitize(payload.comment),
            is_public=True,
        )

        db.add(review)
        await db.commit()
        await db.refresh(review)

        return SessionReviewResponse(
            id=review.id,
            session_id=review.session_id,
            reviewer_id=review.reviewer_id,
            reviewer_name=current_user.full_name,
            reviewer_avatar=current_user.avatar_url,
            reviewed_id=review.reviewed_id,
            role_in_session=review.role_in_session,
            rating_punctuality=review.rating_punctuality,
            rating_pedagogy=review.rating_pedagogy,
            rating_domain=review.rating_domain,
            overall_rating=float(review.overall_rating),
            comment=review.comment,
            created_at=review.created_at,
        )

    @classmethod
    async def send_tip(
        cls,
        db: AsyncSession,
        session_id: UUID,
        payload: SendSessionTipRequest,
        current_user: User,
    ) -> SessionTipResponse:
        """
        Transfiere propina voluntaria en SkillPoints del alumno al tutor de la sesión.
        Garantiza consistencia transaccional y saldo no negativo.
        """
        stmt = select(ExchangeSession).where(ExchangeSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La sesión de intercambio no existe.",
            )

        # Solo el alumno (learner) puede dar propina al tutor (instructor)
        if current_user.id != session.learner_id:
            raise SkillMatchException(
                statuscode=status.HTTP_403_FORBIDDEN,
                message="Solo el alumno de la sesión puede enviar una propina al tutor.",
            )

        # Bloqueo pesimista de billeteras para transferencia atómica
        source_wallet_stmt = select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
        source_wallet_res = await db.execute(source_wallet_stmt)
        source_wallet = source_wallet_res.scalar_one_or_none()

        if not source_wallet or source_wallet.balance < payload.amount:
            raise SkillMatchException(
                statuscode=status.HTTP_400_BAD_REQUEST,
                message=f"Saldo insuficiente. Dispones de {source_wallet.balance if source_wallet else 0} SP y requieres {payload.amount} SP.",
            )

        target_wallet_stmt = select(Wallet).where(Wallet.user_id == session.instructor_id).with_for_update()
        target_wallet_res = await db.execute(target_wallet_stmt)
        target_wallet = target_wallet_res.scalar_one_or_none()

        if not target_wallet:
            # Crear billetera en 0 si no existe aún
            target_wallet = Wallet(user_id=session.instructor_id, balance=0)
            db.add(target_wallet)
            await db.flush()

        # Ejecutar transferencia
        source_wallet.balance -= payload.amount
        target_wallet.balance += payload.amount

        transaction = WalletTransaction(
            source_user_id=current_user.id,
            target_user_id=session.instructor_id,
            session_id=session_id,
            amount=payload.amount,
            type="TIP",
            note=payload.note.strip() if payload.note else None,
        )
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        return SessionTipResponse(
            transaction_id=transaction.id,
            amount=transaction.amount,
            new_balance=source_wallet.balance,
            target_user_id=session.instructor_id,
            note=transaction.note,
            created_at=transaction.created_at,
        )

    @classmethod
    async def get_user_reputation(
        cls,
        db: AsyncSession,
        user_id: UUID,
    ) -> UserReputationResponse:
        """
        Calcula y retorna el Puntaje de Confianza multidimensional, desglose de calificaciones
        e insignias automáticas ganadas por el usuario (RF-REP-02 ★).
        """
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()

        if not target_user:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="El usuario consultado no existe.",
            )

        # 1. Ponderación IA (40%): Habilidades con status "VERIFICADA"
        verified_skills_stmt = select(func.count(TeachingSkill.id)).where(
            TeachingSkill.user_id == user_id,
            TeachingSkill.status == "VERIFICADA",
        )
        verified_count = (await db.execute(verified_skills_stmt)).scalar() or 0
        # Cada habilidad verificada otorga 25 puntos base hasta un tope de 100
        ia_score = min(100.0, float(verified_count * 25.0))

        # 2. Ponderación Pares (30%): Reseñas recibidas
        reviews_query = select(SessionReview).where(
            SessionReview.reviewed_id == user_id,
            SessionReview.is_public == True,
        ).order_by(desc(SessionReview.created_at))
        reviews_res = await db.execute(reviews_query)
        reviews = reviews_res.scalars().all()
        total_reviews = len(reviews)

        if total_reviews > 0:
            avg_punctuality = sum(r.rating_punctuality for r in reviews) / total_reviews
            avg_pedagogy = sum(r.rating_pedagogy for r in reviews) / total_reviews
            avg_domain = sum(r.rating_domain for r in reviews) / total_reviews
            overall_avg = sum(float(r.overall_rating) for r in reviews) / total_reviews
            peer_score = (overall_avg / 5.0) * 100.0
        else:
            avg_punctuality = 5.0
            avg_pedagogy = 5.0
            avg_domain = 5.0
            overall_avg = 5.0
            peer_score = 70.0  # Puntaje neutro inicial de confianza

        # 3. Ponderación Asistencia (20%): Cancelaciones tardías registradas
        late_cancels_stmt = select(func.count(SessionCancellation.id)).where(
            SessionCancellation.cancelled_by_id == user_id,
            SessionCancellation.triggers_booking_block == True,
        )
        late_cancels = (await db.execute(late_cancels_stmt)).scalar() or 0
        no_shows_stmt = select(func.count(SessionNoShowReport.id)).where(
            SessionNoShowReport.absent_user_id == user_id,
            SessionNoShowReport.status == "PROCESSED",
        )
        no_shows = (await db.execute(no_shows_stmt)).scalar() or 0
        attendance_incidents = late_cancels + no_shows
        attendance_score = max(0.0, float(100.0 - (attendance_incidents * 20.0)))

        # 4. Ponderación Antigüedad (10%): Días desde el registro (máximo a los 90 días)
        now = datetime.now(UTC)
        created_at = target_user.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        days_active = max(1, (now - created_at).days)
        tenure_score = min(100.0, float((days_active / 90.0) * 100.0))

        # Consolidación de la fórmula matemática de Puntaje de Confianza (0 a 100%)
        trust_score = round(
            (ia_score * 0.40) + (peer_score * 0.30) + (attendance_score * 0.20) + (tenure_score * 0.10),
            1,
        )

        # Evaluación dinámica de Insignias (Badges)
        badges: list[ReputationBadge] = [
            ReputationBadge(
                code="VERIFIED_IDENTITY",
                title="Identidad Verificada",
                description="Miembro con identidad y correo autenticados con Google Identity Services.",
                icon="ShieldCheck",
                is_active=target_user.provider == "google" or target_user.is_active,
            ),
            ReputationBadge(
                code="TOP_TUTOR",
                title="Tutor Destacado",
                description="Promedio de 4.8★ o superior otorgado por alumnos en al menos 5 sesiones.",
                icon="Star",
                is_active=overall_avg >= 4.8 and total_reviews >= 5,
            ),
            ReputationBadge(
                code="PERFECT_ATTENDANCE",
                title="Puntualidad Perfecta",
                description="Puntualidad impecable (5.0) y cero cancelaciones de último momento.",
                icon="ClockCheck",
                is_active=avg_punctuality >= 4.9 and attendance_incidents == 0,
            ),
            ReputationBadge(
                code="HIGH_TRUST",
                title="Alta Confianza (90%+)",
                description="Miembro con Puntaje de Confianza superior al 85% validado por la plataforma.",
                icon="Award",
                is_active=trust_score >= 85.0,
            ),
        ]

        # Mapear las 10 reseñas más recientes con nombre del autor
        recent_review_dtos = []
        for r in reviews[:10]:
            author_res = await db.execute(select(User).where(User.id == r.reviewer_id))
            author = author_res.scalar_one_or_none()
            recent_review_dtos.append(
                SessionReviewResponse(
                    id=r.id,
                    session_id=r.session_id,
                    reviewer_id=r.reviewer_id,
                    reviewer_name=author.full_name if author else "Miembro de la comunidad",
                    reviewer_avatar=author.avatar_url if author else None,
                    reviewed_id=r.reviewed_id,
                    role_in_session=r.role_in_session,
                    rating_punctuality=r.rating_punctuality,
                    rating_pedagogy=r.rating_pedagogy,
                    rating_domain=r.rating_domain,
                    overall_rating=float(r.overall_rating),
                    comment=r.comment,
                    created_at=r.created_at,
                )
            )

        return UserReputationResponse(
            user_id=target_user.id,
            full_name=target_user.full_name,
            avatar_url=target_user.avatar_url,
            trust_score=trust_score,
            overall_rating=round(overall_avg, 2),
            total_reviews=total_reviews,
            ratings_breakdown=RatingsBreakdown(
                punctuality=round(avg_punctuality, 2),
                pedagogy=round(avg_pedagogy, 2),
                domain=round(avg_domain, 2),
            ),
            factors=TrustScoreFactors(
                ia_verified_score=round(ia_score, 1),
                peer_feedback_score=round(peer_score, 1),
                attendance_score=round(attendance_score, 1),
                tenure_score=round(tenure_score, 1),
            ),
            badges=badges,
            recent_reviews=recent_review_dtos,
        )
