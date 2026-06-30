from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.core.database import get_firestore
from app.schemas.mention_schema import MentionCreate, MentionResponse, MentionUpdate
from typing import List

router = APIRouter(prefix="/mentions", tags=["Gestion des Mentions"])

@router.post("/", response_model=MentionResponse, status_code=status.HTTP_201_CREATED)
def create_mention(mention_in: MentionCreate, firestore_client: Client = Depends(get_firestore)):
    """Créer une nouvelle mention (Réservé Admin à l'avenir)."""
    mention_ref = firestore_client.collection("mentions").document(mention_in.code.upper())
    
    # Vérifier si elle existe déjà
    if mention_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La mention avec le code {mention_in.code} existe déjà."
        )
    
    mention_data = {
        "id": mention_in.code.upper(),
        "code": mention_in.code.upper(),
        "nom": mention_in.nom,
        "parcours": mention_in.parcours
    }
    
    mention_ref.set(mention_data)
    return mention_data

@router.get("/", response_model=List[MentionResponse])
def get_all_mentions(firestore_client: Client = Depends(get_firestore)):
    """Récupérer la liste de toutes les mentions de l'EMIT (Accessible par les étudiants)."""
    mentions_docs = firestore_client.collection("mentions").get()
    mentions = []
    
    for doc in mentions_docs:
        mentions.append(doc.to_dict())
        
    return mentions

@router.get("/{code}", response_model=MentionResponse)
def get_mention_by_code(code: str, firestore_client: Client = Depends(get_firestore)):
    """Récupérer les détails d'une mention via son code (ex: DAII)."""
    mention_ref = firestore_client.collection("mentions").document(code.upper())
    doc = mention_ref.get()
    
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mention introuvable."
        )
        
    return doc.to_dict()

@router.put("/{code}", response_model=MentionResponse)
def update_mention(code: str, mention_in: MentionUpdate, firestore_client: Client = Depends(get_firestore)):
    """Modifier une mention existante."""
    mention_ref = firestore_client.collection("mentions").document(code.upper())
    doc = mention_ref.get()
    
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mention introuvable."
        )
    
    # Filtrer uniquement les champs envoyés (non Null)
    update_data = {k: v for k, v in mention_in.model_dump().items() if v is not None}
    
    if update_data:
        mention_ref.update(update_data)
        
    return mention_ref.get().to_dict()

@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mention(code: str, firestore_client: Client = Depends(get_firestore)):
    """Supprimer une mention."""
    mention_ref = firestore_client.collection("mentions").document(code.upper())
    
    if not mention_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mention introuvable."
        )
        
    mention_ref.delete()
    return None