from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session
from trainops_common.database import get_session
from trainops_common.security import Principal, verify_api_token

DbSession = Annotated[Session, Depends(get_session)]
Authed = Annotated[Principal, Depends(verify_api_token)]

