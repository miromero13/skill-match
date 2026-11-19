import io
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.passport import MyPassportSummaryResponse, PublicPassportResponse
from app.schemas.response import APIResponse
from app.services.passport_service import PassportService

router = APIRouter(
    prefix="/passports",
    tags=["Passports (HU-41)"],
)


def _get_base_urls(request: Request) -> tuple[str, str]:
    """
    Obtiene las URLs base del frontend y backend para conformar los enlaces públicos.
    """
    frontend_origin = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    backend_origin = str(request.base_url).rstrip("/")
    return frontend_origin, backend_origin


@router.get(
    "/me",
    response_model=APIResponse[MyPassportSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Consultar enlace y resumen de pasaporte propio (HU-41 / RF-HAB-11)",
    description="Permite al miembro autenticado obtener su UUID público y URLs para compartir su Pasaporte.",
)
async def get_my_passport_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyPassportSummaryResponse]:
    frontend_url, api_url = _get_base_urls(request)
    summary = MyPassportSummaryResponse(
        public_uuid=current_user.id,
        shareable_url=f"{frontend_url}/passport/{current_user.id}",
        qr_endpoint_url=f"{api_url}/api/passports/{current_user.id}/qr",
        pdf_download_url=f"{api_url}/api/passports/{current_user.id}/pdf",
    )
    return APIResponse.ok(
        data=summary,
        message="Resumen de pasaporte obtenido exitosamente.",
    )


@router.get(
    "/{public_uuid}",
    response_model=APIResponse[PublicPassportResponse],
    status_code=status.HTTP_200_OK,
    summary="Consulta pública del Pasaporte de Habilidades (HU-41 / RF-HAB-11)",
    description="Endpoint público sin autenticación para que terceros y reclutadores auditen competencias y confianza.",
)
async def get_public_passport(
    public_uuid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PublicPassportResponse]:
    frontend_url, api_url = _get_base_urls(request)
    passport = await PassportService.get_public_passport(
        db=db,
        public_uuid=public_uuid,
        base_frontend_url=frontend_url,
        base_api_url=api_url,
    )
    return APIResponse.ok(
        data=passport,
        message="Pasaporte de habilidades verificado y auditado exitosamente.",
    )


@router.get(
    "/{public_uuid}/qr",
    status_code=status.HTTP_200_OK,
    summary="Generar código QR dinámico del Pasaporte (HU-41 / RF-HAB-11)",
    description="Genera en memoria y retorna en streaming la imagen PNG del código QR que apunta a la URL pública.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Imagen PNG del código QR",
        }
    },
)
async def get_passport_qr_image(
    public_uuid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    frontend_url, api_url = _get_base_urls(request)
    # Validar existencia del usuario
    await PassportService.get_public_passport(
        db=db,
        public_uuid=public_uuid,
        base_frontend_url=frontend_url,
        base_api_url=api_url,
    )
    target_url = f"{frontend_url}/passport/{public_uuid}"
    qr_png = PassportService.generate_qr_png_bytes(target_url)

    return StreamingResponse(
        io.BytesIO(qr_png),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/{public_uuid}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Generar y descargar Pasaporte de Habilidades en PDF (HU-41 / RF-HAB-12)",
    description="Genera y transmite en descarga el documento PDF firmado con membrete institucional de SkillMatch.",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Documento PDF firmado",
        }
    },
)
async def download_passport_pdf(
    public_uuid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    frontend_url, api_url = _get_base_urls(request)
    passport = await PassportService.get_public_passport(
        db=db,
        public_uuid=public_uuid,
        base_frontend_url=frontend_url,
        base_api_url=api_url,
    )
    pdf_bytes = PassportService.generate_passport_pdf(passport)

    filename = f"pasaporte-skillmatch-{public_uuid}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
