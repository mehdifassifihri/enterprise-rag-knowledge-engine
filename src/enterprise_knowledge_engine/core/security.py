import hashlib
import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from enterprise_knowledge_engine.core.config import Settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    tenant_id: UUID | None


def authenticate_api_key(config: Settings, api_key: str | None) -> Principal | None:
    if (
        api_key is not None
        and hashlib.sha256(api_key.encode()).hexdigest() in config.revoked_api_key_hashes
    ):
        return None
    bindings = [(config.api_key_tenant_id, config.api_key)] + list(config.tenant_api_keys.items())
    principal = None
    for tenant_id, expected in bindings:
        if api_key is not None and secrets.compare_digest(
            api_key.encode(), expected.get_secret_value().encode()
        ):
            principal = Principal(tenant_id=tenant_id)
    return principal


def require_api_key(
    request: Request, api_key: Annotated[str | None, Security(api_key_header)]
) -> Principal:
    principal = authenticate_api_key(request.app.state.settings, api_key)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    request.state.tenant_id = principal.tenant_id
    return principal


def require_tenant(principal: Annotated[Principal, Depends(require_api_key)]) -> UUID:
    if principal.tenant_id is None:
        raise HTTPException(status_code=403, detail="API key has no tenant binding")
    return principal.tenant_id


TenantIdentity = Annotated[UUID, Depends(require_tenant)]
