from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.core.database import get_firestore
from app.routers.deps import get_current_user
from app.schemas.dossier_schema import DossierCreate, DossierResponse

router = APIRouter(prefix="/dossiers", tags=["Dossiers d'Inscription"])


# ── Créer le dossier ──────────────────────────────────────────────────────────

@router.post("/", response_model=DossierResponse, status_code=status.HTTP_201_CREATED)
def create_dossier(
    dossier_in: DossierCreate,
    current_user: dict = Depends(get_current_user),
    firestore_client: Client = Depends(get_firestore),
):
    """
    Créer le dossier d'inscription de l'étudiant connecté.
    
    - Un seul dossier actif par étudiant : si un dossier existe déjà
      avec un statut autre que 'annule', la requête est rejetée (409).
    - Les 4 champs de documents sont initialisés à null
      (photo, baccalaureat, cin, bordereau).
    """
    user_uid = current_user["uid"]
    dossier_ref = firestore_client.collection("dossiers_inscription").document(user_uid)

    # ── Guard : un seul dossier actif par étudiant ────────────────────────────
    existing = dossier_ref.get()
    if existing.exists:
        statut_actuel = existing.to_dict().get("statut", "")
        if statut_actuel != "annule":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Vous avez déjà un dossier actif "
                    f"(statut : {statut_actuel}). "
                    "Annulez-le avant d'en créer un nouveau."
                ),
            )

    # ── Vérifier que la mention existe ───────────────────────────────────────
    mention_ref = firestore_client.collection("mentions").document(
        dossier_in.mention_code.upper()
    )
    if not mention_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La mention spécifiée n'existe pas.",
        )

    # ── Créer le document Firestore ──────────────────────────────────────────
    dossier_data = {
        "id":                 user_uid,
        "utilisateur_id":     user_uid,
        "mention_code":       dossier_in.mention_code.upper(),
        "parcours":           dossier_in.parcours,
        "reference_bancaire": dossier_in.reference_bancaire.strip(),
        "statut":             "en_attente",   # snake_case — aligné avec le client
        "documents": {
            "photo":        None,
            "baccalaureat": None,
            "cin":          None,
            "bordereau":    None,
        },
        "commentaire": "",
    }

    dossier_ref.set(dossier_data)
    return dossier_data


# ── Consulter son dossier ─────────────────────────────────────────────────────

@router.get("/mon-dossier", response_model=DossierResponse)
def get_my_dossier(
    current_user: dict = Depends(get_current_user),
    firestore_client: Client = Depends(get_firestore),
):
    """Consulter son propre dossier (étudiant connecté)."""
    dossier_ref = firestore_client.collection("dossiers_inscription").document(
        current_user["uid"]
    )
    doc = dossier_ref.get()

    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vous n'avez pas encore créé de dossier d'inscription.",
        )

    return doc.to_dict()


# ── Annuler sa demande ────────────────────────────────────────────────────────

@router.delete(
    "/mon-dossier/annuler",
    response_model=DossierResponse,
    summary="Annuler la demande d'inscription",
)
def annuler_dossier(
    current_user: dict = Depends(get_current_user),
    firestore_client: Client = Depends(get_firestore),
):
    """
    Annuler la demande d'inscription.
    
    - Uniquement possible si le statut est **en_attente**.
    - Passe le statut à **annule** (sans supprimer le document).
    - L'étudiant pourra ensuite soumettre un nouveau dossier.
    """
    user_uid    = current_user["uid"]
    dossier_ref = firestore_client.collection("dossiers_inscription").document(user_uid)
    doc         = dossier_ref.get()

    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun dossier trouvé.",
        )

    data = doc.to_dict()

    if data.get("statut") != "en_attente":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "L'annulation n'est possible que si le dossier est "
                "en statut 'en_attente'. "
                f"Statut actuel : {data.get('statut')}."
            ),
        )

    data["statut"] = "annule"
    dossier_ref.set(data)
    return data
