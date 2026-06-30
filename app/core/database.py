import json
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client
from app.core.config import settings

# Initialisation unique du SDK Firebase Admin
if not firebase_admin._apps:
    if settings.FIREBASE_CREDENTIALS_JSON:
        # Production (Render) : credentials passés en variable d'environnement
        cred_dict = json.loads(settings.FIREBASE_CREDENTIALS)
        cred = credentials.Certificate(cred_dict)
    else:
        # Développement local : credentials depuis un fichier
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)

# Client Firestore pour interagir avec la base de données NoSQL
db = firestore.client()

def get_firestore() -> Client:
    return db
