from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.core.database import get_firestore
from app.core.security import get_password_hash, verify_password, create_access_token
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter(prefix="/admin", tags=["Administration (EMIT)"])

# ─── Schémas ────────────────────────────────────────────────────────────────

class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str

class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: dict

class AdminCreateIn(BaseModel):
    fullName: str
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(..., example="admin")  # super_admin | admin | moderator
    permissions: List[str] = []

class AdminPermissionsIn(BaseModel):
    role: str
    permissions: List[str]

class VerificationIn(BaseModel):
    statut: str = Field(..., example="Validé")  # valeurs françaises : "Validé", "Refusé", "En attente", "Correction demandée"
    commentaire: Optional[str] = None

# ─── Modèle de réponse dossier enrichi avec infos étudiant ──────────────────

class DossierAvecEtudiant(BaseModel):
    """Dossier complet avec les informations personnelles de l'étudiant."""
    # Identifiants
    id: str
    utilisateur_id: str
    # Infos personnelles de l'étudiant (jointure avec collection utilisateurs)
    student_nom: str
    student_prenom: str
    student_email: str
    # Infos dossier
    mention_code: str
    parcours: str
    reference_bancaire: str
    statut: str
    documents: dict
    commentaire: Optional[str] = None

    class Config:
        from_attributes = True

# ─── Seed helper ────────────────────────────────────────────────────────────

def seed_admin_if_empty(db: Client):
    """Crée deux comptes admin de test si la collection est vide."""
    admins_ref = db.collection("admins")
    if len(admins_ref.limit(1).get()) == 0:
        seed = [
            {
                "id": "ADM-001",
                "fullName": "Dr. Rakotomalala Jean",
                "email": "rakotomalala@emit.mg",
                "hashed_password": get_password_hash("Admin1234!"),
                "role": "super_admin",
                "permissions": [
                    "manage_students", "validate_dossiers",
                    "manage_programs", "manage_admins",
                    "view_reports", "manage_documents"
                ],
                "isActive": True,
                "createdAt": "2023-01-15T00:00:00",
                "createdBy": None,
            },
            {
                "id": "ADM-002",
                "fullName": "Razafindrakoto Marie",
                "email": "razafindrakoto@emit.mg",
                "hashed_password": get_password_hash("Admin5678!"),
                "role": "admin",
                "permissions": [
                    "manage_students", "validate_dossiers", "view_reports"
                ],
                "isActive": True,
                "createdAt": "2023-06-01T00:00:00",
                "createdBy": "ADM-001",
            },
        ]
        for a in seed:
            admins_ref.document(a["id"]).set(a)

# ─── Helper : jointure dossier + utilisateur ────────────────────────────────

def _enrich_dossier(dossier_data: dict, db: Client) -> dict:
    """
    Enrichit un dossier avec les infos personnelles de l'étudiant
    en faisant une jointure sur la collection 'utilisateurs'.
    Renvoie toujours un dict valide même si l'utilisateur est introuvable.
    """
    uid = dossier_data.get("utilisateur_id") or dossier_data.get("id", "")
    student_nom = ""
    student_prenom = ""
    student_email = ""

    if uid:
        user_doc = db.collection("utilisateurs").document(uid).get()
        if user_doc.exists:
            user = user_doc.to_dict()
            student_nom    = user.get("nom", "")
            student_prenom = user.get("prenom", "")
            student_email  = user.get("email", "")

    return {
        **dossier_data,
        "student_nom":    student_nom,
        "student_prenom": student_prenom,
        "student_email":  student_email,
    }

# ─── Auth ────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=AdminTokenResponse)
def admin_login(body: AdminLoginIn, db: Client = Depends(get_firestore)):
    """Connexion administrateur — renvoie un JWT."""
    seed_admin_if_empty(db)

    results = db.collection("admins").where("email", "==", body.email).get()
    if not results:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Compte administrateur introuvable.")

    admin_data = results[0].to_dict()

    if not admin_data.get("isActive", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Ce compte est désactivé.")

    if not verify_password(body.password, admin_data["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Mot de passe incorrect.")

    token = create_access_token(subject=admin_data["id"])
    safe = {k: v for k, v in admin_data.items() if k != "hashed_password"}
    return {"access_token": token, "token_type": "bearer", "admin": safe}

# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Client = Depends(get_firestore)):
    """Statistiques globales pour le tableau de bord."""
    dossiers = [d.to_dict() for d in db.collection("dossiers_inscription").get()]
    admins_count   = len(db.collection("admins").get())
    students_count = len(
        db.collection("utilisateurs").where("role", "==", "candidat").get()
    )

    # Supporte les deux jeux de valeurs (français & anglais) pour robustesse
    pending  = sum(1 for d in dossiers if d.get("statut") in ("pending",   "En attente"))
    approved = sum(1 for d in dossiers if d.get("statut") in ("approved",  "Validé"))
    rejected = sum(1 for d in dossiers if d.get("statut") in ("rejected",  "Refusé"))

    return {
        "totalStudents":    students_count,
        "pendingDossiers":  pending,
        "approvedDossiers": approved,
        "rejectedDossiers": rejected,
        "totalAdmins":      admins_count,
    }

# ─── Dossiers (enrichis avec infos étudiant) ─────────────────────────────────

@router.get("/dossiers", response_model=List[DossierAvecEtudiant])
def get_all_dossiers(statut: Optional[str] = None, db: Client = Depends(get_firestore)):
    """
    Liste tous les dossiers enrichis avec les infos personnelles des étudiants.
    Filtre optionnel sur le statut (valeurs françaises : 'En attente', 'Validé', 'Refusé', 'Correction demandée').
    """
    ref = db.collection("dossiers_inscription")
    docs = ref.where("statut", "==", statut).get() if statut else ref.get()

    enriched = []
    for doc in docs:
        data = doc.to_dict()
        enriched.append(_enrich_dossier(data, db))
    return enriched

@router.get("/dossiers/{dossier_id}", response_model=DossierAvecEtudiant)
def get_dossier_by_id(dossier_id: str, db: Client = Depends(get_firestore)):
    """Récupère un dossier par son ID, enrichi avec les infos de l'étudiant."""
    doc = db.collection("dossiers_inscription").document(dossier_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    return _enrich_dossier(doc.to_dict(), db)

@router.post("/dossiers/{dossier_id}/verifier", response_model=DossierAvecEtudiant)
def verifier_dossier(
    dossier_id: str,
    decision: VerificationIn,
    db: Client = Depends(get_firestore)
):
    """
    Valider ou rejeter un dossier.
    Statuts acceptés : 'Validé', 'Refusé', 'En attente', 'Correction demandée'.
    """
    STATUTS_VALIDES = {"En attente", "Validé", "Refusé", "Correction demandée"}
    statut_recu = (decision.statut or "").strip()
    if statut_recu not in STATUTS_VALIDES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Statut invalide reçu : {statut_recu!r}. "
                f"Valeurs acceptées : {sorted(STATUTS_VALIDES)}"
            )
        )
    decision.statut = statut_recu

    ref = db.collection("dossiers_inscription").document(dossier_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Dossier introuvable.")

    data = doc.to_dict()
    data["statut"]     = decision.statut
    data["commentaire"] = decision.commentaire or ""
    ref.set(data)

    return _enrich_dossier(data, db)

# ─── Admins CRUD ─────────────────────────────────────────────────────────────

@router.get("/admins")
def list_admins(db: Client = Depends(get_firestore)):
    """Liste tous les administrateurs (sans les mots de passe)."""
    seed_admin_if_empty(db)
    docs = db.collection("admins").get()
    return [{k: v for k, v in d.to_dict().items() if k != "hashed_password"}
            for d in docs]

@router.post("/admins", status_code=status.HTTP_201_CREATED)
def create_admin(body: AdminCreateIn, db: Client = Depends(get_firestore)):
    """Créer un nouvel administrateur."""
    existing = db.collection("admins").where("email", "==", body.email).get()
    if existing:
        raise HTTPException(status_code=400,
                            detail="Un administrateur avec cet email existe déjà.")
    admin_id = f"ADM-{str(uuid.uuid4())[:8].upper()}"
    doc = {
        "id":              admin_id,
        "fullName":        body.fullName,
        "email":           body.email,
        "hashed_password": get_password_hash(body.password),
        "role":            body.role,
        "permissions":     body.permissions,
        "isActive":        True,
        "createdAt":       datetime.utcnow().isoformat(),
        "createdBy":       None,
    }
    db.collection("admins").document(admin_id).set(doc)
    return {k: v for k, v in doc.items() if k != "hashed_password"}

@router.patch("/admins/{admin_id}/permissions")
def update_permissions(admin_id: str, body: AdminPermissionsIn,
                       db: Client = Depends(get_firestore)):
    """Modifier le rôle et les permissions d'un admin."""
    ref = db.collection("admins").document(admin_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Administrateur introuvable.")
    ref.update({"role": body.role, "permissions": body.permissions})
    updated = ref.get().to_dict()
    return {k: v for k, v in updated.items() if k != "hashed_password"}

@router.patch("/admins/{admin_id}/toggle-status")
def toggle_status(admin_id: str, db: Client = Depends(get_firestore)):
    """Activer / désactiver un compte admin."""
    ref = db.collection("admins").document(admin_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Administrateur introuvable.")
    current = doc.to_dict().get("isActive", True)
    ref.update({"isActive": not current})
    updated = ref.get().to_dict()
    return {k: v for k, v in updated.items() if k != "hashed_password"}

@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(admin_id: str, db: Client = Depends(get_firestore)):
    """Supprimer un administrateur."""
    ref = db.collection("admins").document(admin_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Administrateur introuvable.")
    ref.delete()
