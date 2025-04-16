import base64
import json
from fastapi import Request

def get_user_from_request(request: Request):
    encoded = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not encoded:
        return None
    decoded = base64.b64decode(encoded).decode('utf-8')
    return json.loads(decoded)

# Import other modules to make them available when importing from app.auth
from app.auth.jwt import *
from app.auth.oauth import *