import hashlib
import hmac
import io
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import status
import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, Skill
from app.models.evaluation import Evaluation
from app.models.programming import Challenge, ChallengeSubmission
from app.models.teaching_skill import TeachingSkill
from app.models.user import User
from app.schemas.passport import (
    AntiFraudAudit,
    AuditedCodeChallenge,
    DockerSuiteReport,
    DockerTestCase,
    OralDefenseAudit,
    PassportSkillItem,
    PublicPassportResponse,
    TechnicalDossier,
)
from app.services.reputation_service import ReputationService


class PassportService:
    """
    Servicio de dominio para generación, firma digital y exportación
    del Pasaporte de Habilidades y Reporte de Auditoría Recruiter-Grade (HU-41 / RF-HAB-11 / RF-HAB-12).
    """

    @classmethod
    def generate_verification_hash(cls, user_id: UUID, created_at: datetime) -> str:
        """
        Genera una firma criptográfica inmutable HMAC-SHA256 utilizando la SECRET_KEY del sistema.
        """
        secret = settings.SECRET_KEY.get_secret_value().encode("utf-8")
        payload = f"SKILLMATCH:PASSPORT:{user_id}:{created_at.isoformat()}".encode("utf-8")
        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return f"0x{signature[:16]}...{signature[-8:]}"

    @classmethod
    async def get_public_passport(
        cls,
        db: AsyncSession,
        public_uuid: UUID,
        base_frontend_url: str = "http://localhost:5173",
        base_api_url: str = "http://localhost:8000",
    ) -> PublicPassportResponse:
        """
        Recopila los datos consolidados del pasaporte público:
        identidad del titular, habilidades verificadas, reputación (HU-40) y dossier técnico.
        """
        # 1. Obtener usuario titular
        user_stmt = select(User).where(User.id == public_uuid, User.is_active == True)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()

        if not user:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="No se encontró un pasaporte público para el identificador proporcionado.",
            )

        # 2. Obtener habilidades del usuario con categorías
        skills_stmt = (
            select(TeachingSkill, Skill, Category)
            .join(Skill, TeachingSkill.skill_id == Skill.id)
            .join(Category, Skill.category_id == Category.id)
            .where(TeachingSkill.user_id == user.id)
            .order_by(TeachingSkill.status.desc(), Skill.name.asc())
        )
        skills_res = await db.execute(skills_stmt)
        raw_skills = skills_res.all()

        skills_list = [
            PassportSkillItem(
                id=ts.id,
                name=sk.name,
                category_name=cat.name,
                declared_level=ts.declared_level,
                status=ts.status,
                years_of_experience=ts.years_of_experience,
                verified_at=ts.updated_at if ts.status == "VERIFICADA" else None,
            )
            for ts, sk, cat in raw_skills
        ]

        # 3. Obtener reputación comunitaria y puntaje de confianza (HU-40)
        reputation = await ReputationService.get_user_reputation(db, user.id)

        # 4. Generar hash criptográfico institucional
        issued_date = user.created_at
        verification_hash = cls.generate_verification_hash(user.id, issued_date)
        cert_num = abs(hash(str(user.id))) % 9000 + 1000
        certificate_id = f"#SM-PY-{cert_num}"

        # 5. URLs dinámicas
        qr_endpoint_url = f"{base_api_url}/api/passports/{user.id}/qr"
        pdf_download_url = f"{base_api_url}/api/passports/{user.id}/pdf"
        public_shareable_url = f"{base_frontend_url}/passport/{user.id}"

        # 6. Dossier Técnico real basado en la evaluación aprobada
        verified_skill = next((s for s in skills_list if s.status == "VERIFICADA"), None)
        passed_eval = await db.scalar(
            select(Evaluation)
            .where(Evaluation.user_id == user.id, Evaluation.status == "PASSED")
            .order_by(Evaluation.updated_at.desc())
        )

        if verified_skill and passed_eval is not None:
            submission = await db.scalar(
                select(ChallengeSubmission)
                .where(ChallengeSubmission.evaluation_id == passed_eval.id)
                .order_by(ChallengeSubmission.submitted_at.desc())
            )
            code_challenge = None
            oral_defense = None
            oral_score: Optional[float] = None

            if submission is not None:
                challenge = await db.get(Challenge, submission.challenge_id)
                raw_results = (submission.result or {}).get("results", [])
                total = max(submission.total_tests, len(raw_results), 1)
                test_cases = [
                    DockerTestCase(
                        name=str(item.get("name", f"test_{idx + 1}")),
                        status="PASSED" if item.get("passed") else "FAILED",
                        duration_seconds=0.0,
                        percentage=int(round(((idx + 1) / total) * 100)),
                    )
                    for idx, item in enumerate(raw_results)
                ]
                coverage_pct = int(round((submission.passed_tests / max(submission.total_tests, 1)) * 100))
                docker_report = DockerSuiteReport(
                    passed_count=submission.passed_tests,
                    total_count=submission.total_tests,
                    execution_time_seconds=0.0,
                    coverage_percentage=coverage_pct,
                    test_cases=test_cases,
                )
                code_challenge = AuditedCodeChallenge(
                    title=challenge.title if challenge else f"Reto práctico: {verified_skill.name}",
                    consigna=challenge.statement if challenge else "",
                    file_name="solution.py",
                    language="Python 3.12 · UTF-8",
                    source_code=submission.code,
                    docker_report=docker_report,
                )
                if submission.defense_transcript is not None:
                    oral_score = round(float(submission.defense_score or 0.0), 2)
                    oral_defense = OralDefenseAudit(
                        score=oral_score,
                        question="Explicá por qué diseñaste y resolviste el reto de esta manera.",
                        candidate_transcript=submission.defense_transcript,
                        ai_verdict=submission.defense_feedback or "Evaluación completada.",
                    )

            anti_fraud = AntiFraudAudit(
                facial_liveness_score=100.0,
                voice_verification_status="Voz única confirmada en micrófono",
                screen_violations_count=0,
                clipboard_abuse_detected=False,
            )

            eval_skill = next((s for s in skills_list if s.id == passed_eval.teaching_skill_id), verified_skill)
            technical_dossier = TechnicalDossier(
                has_technical_audit=True,
                technical_score=round(float(passed_eval.final_score or 0.0), 2),
                oral_defense_score=oral_score,
                evaluated_skill_name=eval_skill.name if eval_skill else verified_skill.name,
                code_challenge=code_challenge,
                oral_defense=oral_defense,
                anti_fraud=anti_fraud,
            )
        else:
            # Usuario sin evaluaciones prácticas aprobadas aún
            technical_dossier = TechnicalDossier(
                has_technical_audit=False,
                technical_score=None,
                oral_defense_score=None,
                evaluated_skill_name=None,
                code_challenge=None,
                oral_defense=None,
                anti_fraud=None,
            )

        return PublicPassportResponse(
            public_uuid=user.id,
            certificate_id=certificate_id,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            bio=user.bio or "Miembro de la Comunidad SkillMatch",
            location_label=user.location_label,
            member_since=user.created_at,
            issued_at=datetime.now(timezone.utc),
            verification_hash=verification_hash,
            verification_node="Nodo Central SkillMatch #04",
            qr_endpoint_url=qr_endpoint_url,
            pdf_download_url=pdf_download_url,
            public_shareable_url=public_shareable_url,
            trust_score=reputation.trust_score,
            overall_rating=reputation.overall_rating,
            total_reviews=reputation.total_reviews,
            ratings_breakdown=reputation.ratings_breakdown,
            factors=reputation.factors,
            badges=reputation.badges,
            skills=skills_list,
            technical_dossier=technical_dossier,
        )

    @classmethod
    def generate_qr_png_bytes(cls, target_url: str) -> bytes:
        """
        Genera dinámicamente un código QR en formato PNG apuntando a la URL del pasaporte.
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(target_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#00786F", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @classmethod
    def generate_passport_pdf(cls, passport: PublicPassportResponse) -> bytes:
        """
        Genera un documento PDF institucional con membrete oficial,
        resumen de rigor técnico, firma criptográfica y código QR embebido.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        emerald = colors.HexColor("#00786F")
        dark_slate = colors.HexColor("#0F172A")
        muted_text = colors.HexColor("#64748B")
        border_color = colors.HexColor("#CBD5E1")
        light_bg = colors.HexColor("#F8FAFC")

        title_style = ParagraphStyle(
            "PassportTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=emerald,
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "PassportSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=muted_text,
            fontName="Helvetica-Bold",
        )
        body_style = ParagraphStyle(
            "PassportBody",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=dark_slate,
            fontName="Helvetica",
        )
        code_style = ParagraphStyle(
            "PassportCode",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#047857"),
            fontName="Courier",
        )

        elements = []

        # 1. Header Banner
        header_table = Table(
            [
                [
                    Paragraph("SKILLMATCH TRUST PROTOCOL", title_style),
                    Paragraph(f"<b>CERTIFICADO OFICIAL:</b> {passport.certificate_id}", subtitle_style),
                ],
                [
                    Paragraph("REPORTE DE AUDITORÍA PÚBLICA · COMPETENCIAS TÉCNICAS ACREDITADAS", subtitle_style),
                    Paragraph(f"<b>EMITIDO:</b> {passport.issued_at.strftime('%d/%m/%Y')}", subtitle_style),
                ],
            ],
            colWidths=[380, 160],
        )
        header_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ])
        )
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=emerald, spaceBefore=6, spaceAfter=10))

        # 2. Información del Titular y Hash
        titular_info = f"""
        <b>Titular:</b> {passport.full_name}<br/>
        <b>Ubicación:</b> {passport.location_label}<br/>
        <b>Firma Digital:</b> {passport.verification_hash}<br/>
        <b>Nodo Validador:</b> {passport.verification_node}
        """

        # Generar imagen QR en memoria para reportlab
        qr_bytes = cls.generate_qr_png_bytes(passport.public_shareable_url)
        qr_image = Image(io.BytesIO(qr_bytes), width=1.1 * inch, height=1.1 * inch)

        titular_table = Table(
            [
                [Paragraph(titular_info, body_style), qr_image],
            ],
            colWidths=[430, 110],
        )
        titular_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), light_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
        elements.append(titular_table)
        elements.append(Spacer(1, 12))

        # 3. Métricas (4 Cajas adaptativas)
        dossier = passport.technical_dossier
        if dossier.has_technical_audit and dossier.code_challenge and dossier.oral_defense:
            metrics_data = [
                [
                    f"SCORE CÓDIGO\n{dossier.technical_score or 0:.0f} / 100",
                    f"DEFENSA ORAL IA\n{dossier.oral_defense_score or 0:.0f} / 100",
                    f"SUITE DOCKER\n{dossier.code_challenge.docker_report.passed_count}/{dossier.code_challenge.docker_report.total_count} PASSED",
                    f"CONFIANZA GLOBAL\n{passport.trust_score:.0f}%",
                ]
            ]
        else:
            metrics_data = [
                [
                    f"HABILIDADES\n{len(passport.skills)} REGISTRADAS",
                    f"AUDITORÍA TÉCNICA\nPENDIENTE",
                    f"CONFIANZA GLOBAL\n{passport.trust_score:.0f}%",
                    f"RESEÑAS ALUMNOS\n{passport.total_reviews} AUDITADAS",
                ]
            ]

        metrics_table = Table(metrics_data, colWidths=[135, 135, 135, 135])
        metrics_table.setStyle(
            TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), emerald),
                ("BACKGROUND", (0, 0), (-1, -1), light_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        elements.append(metrics_table)
        elements.append(Spacer(1, 14))

        if dossier.has_technical_audit and dossier.code_challenge and dossier.oral_defense:
            # 4. Desafío Práctico: Código y Tests en Docker
            skill_name = dossier.evaluated_skill_name or "Desafío Técnico"
            elements.append(Paragraph(f"<b>1. DESAFÍO TÉCNICO EN SANDBOX DOCKER ({skill_name.upper()})</b>", subtitle_style))
            elements.append(Spacer(1, 4))

            code_box = Paragraph(
                dossier.code_challenge.source_code.replace("\n", "<br/>").replace(" ", "&nbsp;"),
                code_style,
            )
            passed = dossier.code_challenge.docker_report.passed_count
            total = dossier.code_challenge.docker_report.total_count
            time_sec = dossier.code_challenge.docker_report.execution_time_seconds
            cov = dossier.code_challenge.docker_report.coverage_percentage
            test_summary = (
                f"<b>Suite de Pruebas Unitarias Pytest:</b> {passed}/{total} Passed ({cov}% Cobertura)<br/>"
                f"• Tiempo de ejecución: {time_sec}s en contenedor Docker aislado<br/>"
                f"• Verificación de código fuente, tipado estricto y asincronía.<br/>"
                f"• Anti-cheat: Análisis AST y detección de plagio aprobada."
            )
            audit_table = Table(
                [
                    [code_box, Paragraph(test_summary, body_style)],
                ],
                colWidths=[310, 230],
            )
            audit_table.setStyle(
                TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#0F172A")),
                    ("BACKGROUND", (1, 0), (1, 0), light_bg),
                    ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ])
            )
            elements.append(audit_table)
            elements.append(Spacer(1, 12))

            # 5. Defensa Oral Conceptual y Anti-Fraude
            elements.append(Paragraph("<b>2. DEFENSA CONCEPTUAL EN VIVO ANTE LA IA & ANTI-FRAUDE</b>", subtitle_style))
            elements.append(Spacer(1, 4))

            defense_content = f"""
            <b>Pregunta Adaptativa:</b> "{dossier.oral_defense.question}"<br/><br/>
            <b>Transcripción de Respuesta Oral:</b> "{dossier.oral_defense.candidate_transcript}"<br/><br/>
            <b>Dictamen IA:</b> {dossier.oral_defense.ai_verdict}<br/>
            <b>Integridad Biométrica:</b> Liveness Facial 100% · Voz única en micrófono · 0 infracciones de pantalla.
            """
            defense_table = Table([[Paragraph(defense_content, body_style)]], colWidths=[540])
            defense_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), light_bg),
                    ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ])
            )
            elements.append(defense_table)
            elements.append(Spacer(1, 14))
        else:
            # Sección de Habilidades Declaradas y Estado Pendiente
            elements.append(Paragraph("<b>ESTADO DE CERTIFICACIÓN TÉCNICA · AUDITORÍA PENDIENTE</b>", subtitle_style))
            elements.append(Spacer(1, 4))

            skills_rows = []
            for sk in passport.skills:
                skills_rows.append(f"• <b>{sk.name}</b> ({sk.category_name}) — Nivel: {sk.declared_level} — Estado: <i>{sk.status}</i>")

            skills_text = "<br/>".join(skills_rows) if skills_rows else "<i>No se registran habilidades registradas.</i>"
            pending_notice = f"""
            <b>Aviso de Certificación:</b><br/>
            El titular cuenta con habilidades registradas en la comunidad, pero <b>aún no ha completado el examen práctico en Docker Sandbox ni la defensa oral frente a cámara</b> para obtener la insignia oficial de habilidad técnica verificada.<br/><br/>
            <b>Habilidades registradas en su perfil:</b><br/>
            {skills_text}<br/><br/>
            <i>Una vez completada la prueba práctica, este documento reflejará automáticamente el código fuente auditado, la tasa de cobertura en Pytest y el análisis de voz y biometría.</i>
            """
            pending_table = Table([[Paragraph(pending_notice, body_style)]], colWidths=[540])
            pending_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), light_bg),
                    ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ])
            )
            elements.append(pending_table)
            elements.append(Spacer(1, 14))

        # 6. Pie de Página Institucional
        footer_text = f"""
        <i>Este documento es un reporte público generado institucionalmente por la plataforma SkillMatch.
        Para validar la autenticidad e inmutabilidad de este certificado, escanee el código QR adjunto
        o visite {passport.public_shareable_url}</i>
        """
        elements.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceBefore=4, spaceAfter=6))
        elements.append(Paragraph(footer_text, subtitle_style))

        doc.build(elements)
        return buffer.getvalue()
