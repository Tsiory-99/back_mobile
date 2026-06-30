import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Inscript_Uf Backend")
    VERSION:      str = os.getenv("VERSION",      "1.0.0")
    API_V1_STR:   str = os.getenv("API_V1_STR",   "/api/v1")
    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")

    # ⚠️ These were missing — required by deps.py for JWT verification
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-default")
    ALGORITHM:  str = os.getenv("ALGORITHM",  "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

settings = Settings()
