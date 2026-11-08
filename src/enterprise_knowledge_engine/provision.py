"""Explicit administrative tenant provisioning: python -m enterprise_knowledge_engine.provision."""

import argparse
from uuid import UUID

from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db.models import Tenant
from enterprise_knowledge_engine.db.session import build_engine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision a tenant for a server-configured API key"
    )
    parser.add_argument("--id", required=True, type=UUID)
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    if (
        not args.name.strip()
        or len(args.name) > 200
        or not args.slug.strip()
        or len(args.slug) > 100
    ):
        parser.error("Require a nonblank name (<=200 characters) and slug (<=100 characters)")
    engine = build_engine(Settings())
    try:
        with Session(engine) as session, session.begin():
            if session.get(Tenant, args.id) is not None:
                print(f"Tenant {args.id} already exists")
                return
            session.add(Tenant(id=args.id, name=args.name, slug=args.slug))
        print(f"Provisioned tenant {args.id}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
