from pydantic import BaseModel, Field
from typing import Optional, Dict
from enum import Enum

class StatutDossier(str, Enum):
    en_attente           = "en_attente"
    valide               = "valide"
    refuse               = "refuse"
    correction_demandee  = "correction_demandee"
    annule               = "annule"

class DossierCreate(BaseModel):
    mention_code:       str = Field(..., example="DAII")
    parcours:           str = Field(..., example="Génie Logiciel")
    reference_bancaire: str = Field(..., example="ABC12345")

class DossierResponse(BaseModel):
    id:                 str
    utilisateur_id:     str
    mention_code:       str
    parcours:           str
    reference_bancaire: str
    statut:             str   # en_attente | valide | refuse | correction_demandee | annule
    documents:          Dict[str, Optional[str]]
    commentaire:        Optional[str] = None

    class Config:
        from_attributes = True
