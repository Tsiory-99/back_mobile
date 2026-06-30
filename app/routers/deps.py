from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import PyJWTError as JWTError
from google.cloud.firestore import Client
from app.core.config import settings
from app.core.database import get_firestore
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
def get_current_user(token: str = Depends(oauth2_scheme), firestore_client: Client = Depends(get_firestore)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée ou jeton invalide. Veuillez vous reconnecter.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_uid: str = payload.get("sub")
        if user_uid is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Aller chercher l'utilisateur dans Firestore
    user_doc = firestore_client.collection("utilisateurs").document(user_uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
        
    return user_doc.to_dict()
