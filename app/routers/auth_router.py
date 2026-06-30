from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.core.database import get_firestore
from app.core.security import get_password_hash, verify_password, create_access_token
from app.schemas.user_schema import UserRegister, UserLogin, TokenResponse, UserResponse
from pydantic import BaseModel, EmailStr
import uuid

router = APIRouter(prefix="/auth", tags=["Authentification"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserRegister, firestore_client: Client = Depends(get_firestore)):
    """Inscrire un nouvel étudiant candidat."""
    users_ref = firestore_client.collection("utilisateurs")
    
    # Vérifier si l'email existe déjà dans Firestore
    existing_users = users_ref.where("email", "==", user_in.email).get()
    if len(existing_users) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette adresse email est déjà enregistrée."
        )
    
    # Préparation du document utilisateur
    user_uid = str(uuid.uuid4())
    hashed_password = get_password_hash(user_in.password)
    
    user_data = {
        "uid": user_uid,
        "email": user_in.email,
        "hashed_password": hashed_password,
        "nom": user_in.nom.upper(),
        "prenom": user_in.prenom,
        "role": "candidat"  # Rôle par défaut
    }
    
    # Enregistrement dans Firestore
    users_ref.document(user_uid).set(user_data)
    
    return user_data

@router.post("/login", response_model=TokenResponse)
def login_user(user_in: UserLogin, firestore_client: Client = Depends(get_firestore)):
    """Connecter un utilisateur et renvoyer son jeton d'accès JWT."""
    users_ref = firestore_client.collection("utilisateurs")
    
    # Rechercher l'utilisateur par son adresse email
    query_results = users_ref.where("email", "==", user_in.email).get()
    if len(query_results) == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects (email introuvable)."
        )
    
    user_doc = query_results[0]
    user_data = user_doc.to_dict()
    
    # Vérification du mot de passe
    if not verify_password(user_in.password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects (mot de passe invalide)."
        )
    
    # Génération du jeton JWT basé sur l'UID de l'utilisateur
    access_token = create_access_token(subject=user_data["uid"])
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "uid": user_data["uid"],
            "email": user_data["email"],
            "nom": user_data["nom"],
            "prenom": user_data["prenom"],
            "role": user_data["role"],
        }
    }

# ─── Route alias pour Flutter (/api/v1/auth/admin/login) ──────────────────────

class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str

class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: dict

@router.post("/admin/login", response_model=AdminTokenResponse, tags=["Administration (EMIT)"])
def admin_login_alias(body: AdminLoginIn, db: Client = Depends(get_firestore)):
    """
    Alias de /api/v1/admin/auth/login — appelé par l'app Flutter.
    Connexion administrateur via email + mot de passe → JWT.
    """
    results = db.collection("admins").where("email", "==", body.email).get()
    if not results:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte administrateur introuvable."
        )

    admin_data = results[0].to_dict()

    if not admin_data.get("isActive", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé."
        )

    if not verify_password(body.password, admin_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect."
        )

    token = create_access_token(subject=admin_data["id"])
    safe = {k: v for k, v in admin_data.items() if k != "hashed_password"}
    return {"access_token": token, "token_type": "bearer", "admin": safe}
