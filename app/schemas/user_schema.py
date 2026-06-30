from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Mot de passe de 6 caractères minimum")
    nom: str
    prenom: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    uid: str
    email: EmailStr
    nom: str
    prenom: str
    role: str  # 'candidat' ou 'admin'

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse