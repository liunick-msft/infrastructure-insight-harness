"""Primary command-line interface for the infrastructure insight harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()

from .catalog import CatalogError
from .inventory import InventoryError
from .models import CollectionState, RunRequest
from .playbooks import PlaybookError
from .service import DEFAULTS_DIR, PreflightError, RuntimePaths, InsightService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="infrastructure-insight")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULTS_DIR / "actions.yaml")
    parser.add_argument("--profiles", type=Path, default=DEFAULTS_DIR / "profiles.yaml")
    parser.add_argument("--playbooks", type=Path, default=DEFAULTS_DIR / "playbooks.yaml")
    parser.add_argument("--profile", default="cautious")
    parser.add_argument(
        "--known-hosts", type=Path, default=Path.home() / ".ssh" / "known_hosts"
    )
    parser.add_argument("--evidence-dir", type=Path)

    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("list-targets")
    subparsers.add_parser("list-actions")
    subparsers.add_parser("list-playbooks")

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--targets", nargs="*")

    run = subparsers.add_parser("run")
    run.add_argument("--targets", nargs="+", required=True)
    run.add_argument("--actions", nargs="+", required=True)

    plan_playbook = subparsers.add_parser("plan-playbook")
    plan_playbook.add_argument("--playbook", required=True)
    plan_playbook.add_argument("--targets", nargs="+", required=True)

    run_playbook = subparsers.add_parser("run-playbook")
    run_playbook.add_argument("--playbook", required=True)
    run_playbook.add_argument("--targets", nargs="+", required=True)
    return parser


def _service(args: argparse.Namespace) -> InsightService:
    return InsightService(
        RuntimePaths(
            inventory=args.inventory,
            known_hosts=args.known_hosts,
            evidence_dir=args.evidence_dir,
            catalog=args.catalog,
            profiles=args.profiles,
            playbooks=args.playbooks,
            profile_id=args.profile,
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        service = _service(args)
        if args.operation == "list-targets":
            payload = service.list_targets()
            success = True
        elif args.operation == "list-actions":
            payload = service.list_actions()
            success = True
        elif args.operation == "list-playbooks":
            payload = service.list_playbooks()
            success = True
        elif args.operation == "preflight":
            checks = service.preflight(tuple(args.targets) if args.targets else None)
            payload = [check.model_dump(mode="json") for check in checks]
            success = all(check.ready for check in checks)
        elif args.operation == "plan-playbook":
            plan = service.plan_playbook(args.playbook, tuple(args.targets))
            payload = plan.model_dump(mode="json")
            success = True
        elif args.operation == "run-playbook":
            result = service.run_playbook(args.playbook, tuple(args.targets))
            payload = result.model_dump(mode="json")
            success = all(
                item.collection_state == CollectionState.SUCCESS for item in result.results
            )
        else:
            result = service.run(
                RunRequest(target_ids=tuple(args.targets), action_ids=tuple(args.actions))
            )
            payload = result.model_dump(mode="json")
            success = all(
                item.collection_state == CollectionState.SUCCESS for item in result.results
            )
    except (
        CatalogError,
        InventoryError,
        PlaybookError,
        PreflightError,
        ValidationError,
        ValueError,
    ) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    print(json.dumps(payload, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
