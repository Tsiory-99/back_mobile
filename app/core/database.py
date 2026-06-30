import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client
from app.core.config import settings

# Initialisation unique du SDK Firebase Admin
if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)

# Client Firestore pour interagir avec la base de données NoSQL
db = firestore.client()

# Fonction utilitaire pour injecter le client Firestore dans nos routes
def get_firestore() -> Client:
    return db