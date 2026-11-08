import argparse
import sys

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Tenant-bound MCP stdio server")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    try:
        create_server(Settings(_env_file=args.env_file)).run()
    except Exception:
        print("MCP startup failed; check credentials, configuration and database", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
