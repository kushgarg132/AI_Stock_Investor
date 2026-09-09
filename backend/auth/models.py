from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    id: str
    google_sub: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime
    # Re-derived from ADMIN_EMAILS on every login, so revoking admin is an
    # env edit plus a re-login rather than a database migration.
    role: str = "user"
