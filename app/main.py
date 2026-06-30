from fastapi import FastAPI, Depends, HTTPException
from firebase_admin import firestore as admin_firestore
from google.cloud.firestore import Client
from app.core.config import settings
from app.core.database import get_firestore
from app.routers import auth_router, mention_router, dossier_router, document_router, admin_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs"
)

# 🛠️ CONFIGURATION DU CORS (À placer juste après l'initialisation de app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise toutes les sources (parfait pour le développement)
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Autorise tous les en-têtes (y compris le Token Authorization)
)

# Inclusion des routes
app.include_router(auth_router.router, prefix=settings.API_V1_STR)
app.include_router(mention_router.router, prefix=settings.API_V1_STR)
app.include_router(dossier_router.router, prefix=settings.API_V1_STR)
app.include_router(document_router.router, prefix=settings.API_V1_STR)
app.include_router(admin_router.router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {"status": "healthy", "project": settings.PROJECT_NAME}

@app.get("/test-firebase")
def test_firebase_connection(firestore_client: Client = Depends(get_firestore)):
    try:
        test_ref = firestore_client.collection("connections_test").document("ping")
        test_ref.set({"status": "connected", "timestamp": admin_firestore.SERVER_TIMESTAMP})
        doc = test_ref.get()
        if doc.exists:
            return {"status": "success", "message": "Connexion à Cloud Firestore établie avec succès !"}
        else:
            raise HTTPException(status_code=500, detail="Document introuvable.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))