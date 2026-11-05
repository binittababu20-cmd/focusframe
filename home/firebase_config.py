try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

firebase_key = BASE_DIR / "firebase-key.json"

if not firebase_admin._apps:
    cred = credentials.Certificate(str(firebase_key))

    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": "https://focusframe-123b6-default-rtdb.firebaseio.com/"
        }
    )