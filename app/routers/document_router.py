from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from google.cloud.firestore import Client
from app.core.database import get_firestore
from app.routers.deps import get_current_user
from app.schemas.dossier_schema import DossierResponse
import base64

router = APIRouter(prefix="/documents", tags=["Téléversement des Documents"])

# ── 4 documents obligatoires (releves supprimé) ───────────────────────────────
ALLOWED_DOC_TYPES = ["photo", "baccalaureat", "cin", "bordereau"]

DOC_LABELS = {
    "photo":        "Photo d'identité",
    "baccalaureat": "Image diplôme du Baccalauréat",
    "cin":          "Image CIN (recto/verso)",
    "bordereau":    "Image bordereau de versement",
}

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/pdf"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 Mo


@router.post("/upload/{doc_type}", response_model=DossierResponse)
def upload_document(
    doc_type: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    firestore_client: Client = Depends(get_firestore),
):
    """
    Téléverser un document obligatoire.

    Types acceptés : photo | baccalaureat | cin | bordereau.
    Formats acceptés : JPG, PNG, PDF (max 5 Mo).
    Le fichier est encodé en Base64 (Data-URI) et stocké dans Firestore.
    Si le dossier était en statut 'correction_demandee', il repasse en 'en_attente'.
    """
    user_uid = current_user["uid"]

    # ── Validation type de document ───────────────────────────────────────────
    if doc_type.lower() not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Type de document invalide : '{doc_type}'. "
                f"Choisissez parmi : {ALLOWED_DOC_TYPES}"
            ),
        )

    # ── Dossier doit exister ──────────────────────────────────────────────────
    dossier_ref = firestore_client.collection("dossiers_inscription").document(user_uid)
    dossier_doc = dossier_ref.get()
    if not dossier_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez d'abord créer votre dossier d'inscription.",
        )

    dossier_data = dossier_doc.to_dict()

    # ── Dossier ne doit pas être annulé ──────────────────────────────────────
    if dossier_data.get("statut") == "annule":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'uploader un document sur un dossier annulé.",
        )

    # ── Validation MIME ───────────────────────────────────────────────────────
    mime_type = file.content_type or "image/jpeg"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Format non supporté : '{mime_type}'. "
                f"Utilisez JPG, PNG ou PDF."
            ),
        )

    # ── Lecture + validation taille ───────────────────────────────────────────
    try:
        file_content = file.file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lecture fichier : {str(e)}",
        )

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux (max 5 Mo).",
        )

    # ── Encodage Base64 → Data-URI ────────────────────────────────────────────
    try:
        encoded = base64.b64encode(file_content).decode("utf-8")
        virtual_url = f"data:{mime_type};base64,{encoded}"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur encodage : {str(e)}",
        )

    # ── Mise à jour Firestore ─────────────────────────────────────────────────
    dossier_data["documents"][doc_type.lower()] = virtual_url

    # Si correction demandée → repasse en attente après re-dépôt
    if dossier_data.get("statut") == "correction_demandee":
        dossier_data["statut"] = "en_attente"

    dossier_ref.set(dossier_data)
    return dossier_data
