from pydantic import BaseModel, Field
from typing import List, Optional  # <--- AJOUTER Optional ICI

class MentionBase(BaseModel):
    code: str = Field(..., example="DAII", description="Code unique de la mention")
    nom: str = Field(..., example="Développement d'Applications Internet et Intranet")
    parcours: List[str] = Field(default=[], example=["Administration de Bases de Données", "Génie Logiciel"])

class MentionCreate(MentionBase):
    pass

class MentionUpdate(BaseModel):
    nom: Optional[str] = None
    parcours: Optional[List[str]] = None

class MentionResponse(MentionBase):
    id: str

    class Config:
        from_attributes = True