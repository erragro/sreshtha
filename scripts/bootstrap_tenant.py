"""Bootstrap a new tenant on a fresh Sreshtha deployment.

Intended for a partner (welfare board, union, sponsor, NGO) standing
up their own instance from this repository. Creates:

  1. A tenant row with slug + name + kind + optional branding.
  2. A first admin user (or reuses one that already matches by email),
     hashed with the same helper the auth surface uses.
  3. A membership binding the user to the tenant as ``owner``.
  4. Sets ``users.default_tenant_id`` on that user so their first login
     lands in the new tenant's context.

Idempotent: re-running with the same ``--slug`` + ``--admin-email``
updates the tenant name / kind / branding + upserts the membership +
resets the password if ``--admin-password`` is provided; skips the
password change otherwise.

Usage (interactive password prompt):

    python -m scripts.bootstrap_tenant \\
        --slug karnataka-welfare \\
        --name "Karnataka Platform Gig Workers Welfare Board" \\
        --kind welfare_board \\
        --admin-email owner@example.gov.in \\
        --tagline "Powered by Sreshtha" \\
        --primary-color "#5b3fd6"

Usage (non-interactive, for scripting / CI):

    SRESHTHA_ADMIN_PASSWORD='...' python -m scripts.bootstrap_tenant \\
        --slug ifat \\
        --name "Indian Federation of App-based Transport Workers" \\
        --kind union \\
        --admin-email admin@ifat.in \\
        --admin-password-env SRESHTHA_ADMIN_PASSWORD
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import uuid
from typing import Optional

from sqlalchemy import select

from app.auth.password import hash_password
from app.db import SessionLocal
from app.models import Tenant, TenantMembership, User


VALID_KINDS = ("welfare_board", "union", "sponsor", "ngo", "internal", "other")
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?$")


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise SystemExit(
            f"Invalid slug '{slug}'. Must be 1-60 chars, lowercase "
            "alnum + hyphens, no leading/trailing hyphen."
        )


def _resolve_password(args) -> Optional[str]:
    if args.admin_password is not None:
        return args.admin_password
    if args.admin_password_env:
        pw = os.environ.get(args.admin_password_env)
        if not pw:
            raise SystemExit(
                f"Env var {args.admin_password_env} is unset. Export it "
                "or use --admin-password."
            )
        return pw
    # Interactive mode: only prompt when creating a new user or when the
    # caller has asked to update. See bootstrap() below.
    if not sys.stdin.isatty():
        return None
    return None


def bootstrap(args) -> None:
    _validate_slug(args.slug)
    if args.kind not in VALID_KINDS:
        raise SystemExit(
            f"Invalid --kind '{args.kind}'. One of: {', '.join(VALID_KINDS)}."
        )

    branding = {}
    if args.tagline:        branding["tagline"] = args.tagline
    if args.primary_color:  branding["primary_color"] = args.primary_color
    if args.logo_url:       branding["logo_url"] = args.logo_url
    if args.native_name:    branding["native_name"] = args.native_name

    with SessionLocal() as db:
        # --- upsert tenant ---
        tenant = db.scalars(select(Tenant).where(Tenant.slug == args.slug)).first()
        if tenant is None:
            tenant = Tenant(
                slug=args.slug,
                name=args.name,
                kind=args.kind,
                status="active",
                contact_email=args.admin_email,
                branding=branding,
                config={},
            )
            db.add(tenant)
            db.flush()
            print(f"[+] Created tenant  slug={tenant.slug}  id={tenant.id}")
        else:
            tenant.name = args.name
            tenant.kind = args.kind
            if branding:
                tenant.branding = branding
            print(f"[·] Reused tenant   slug={tenant.slug}  id={tenant.id}")

        # --- upsert admin user ---
        user = db.scalars(select(User).where(User.email == args.admin_email)).first()
        password = _resolve_password(args)
        if user is None:
            # New user needs a password one way or another.
            if password is None:
                password = getpass.getpass(
                    f"Password for new admin {args.admin_email}: "
                )
            if not password or len(password) < 8:
                raise SystemExit("Password must be at least 8 characters.")
            user = User(
                email=args.admin_email,
                password_hash=hash_password(password),
                is_active=True,
                is_super_admin=True,
                default_tenant_id=tenant.id,
            )
            db.add(user)
            db.flush()
            print(f"[+] Created admin   email={user.email}  id={user.id}")
        else:
            user.default_tenant_id = tenant.id
            if not user.is_super_admin:
                user.is_super_admin = True
            if password:
                user.password_hash = hash_password(password)
                print(f"[·] Reused admin   email={user.email}  (password reset)")
            else:
                print(f"[·] Reused admin   email={user.email}  (password unchanged)")

        # --- upsert membership ---
        membership = db.scalars(
            select(TenantMembership)
            .where(TenantMembership.tenant_id == tenant.id)
            .where(TenantMembership.user_id == user.id)
        ).first()
        if membership is None:
            membership = TenantMembership(
                tenant_id=tenant.id, user_id=user.id, role="owner",
            )
            db.add(membership)
            print(f"[+] Granted role    owner")
        elif membership.role != "owner":
            membership.role = "owner"
            print(f"[·] Upgraded role   {membership.role} → owner")
        else:
            print(f"[·] Kept role       owner")

        db.commit()

        print("")
        print("Done. Sign in at your Sreshtha deployment with:")
        print(f"    email:    {args.admin_email}")
        print(f"    tenant:   {tenant.slug}")
        print("")
        print("Next steps:")
        print(f"  1. Start the app:      uvicorn app.main:app --port 8000")
        print(f"  2. Start the frontend: cd frontend && npm run dev")
        print(f"  3. Sign in and grant module access under /admin")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="scripts.bootstrap_tenant",
        description="Create a Sreshtha tenant + first admin user.",
    )
    ap.add_argument("--slug", required=True,
                    help="URL-safe identifier for the tenant (a-z, 0-9, -).")
    ap.add_argument("--name", required=True,
                    help="Human-readable tenant name.")
    ap.add_argument("--kind", required=True,
                    choices=VALID_KINDS,
                    help="Tenant kind. Drives billing + reporting later.")
    ap.add_argument("--admin-email", required=True,
                    help="Owner user's email. Reused if it already exists.")

    ap.add_argument("--admin-password", default=None,
                    help="Owner password (inline). Prefer --admin-password-env.")
    ap.add_argument("--admin-password-env", default=None,
                    help="Name of env var holding the owner password.")

    # Optional branding fields — stored as branding JSON on the tenant.
    ap.add_argument("--tagline", default=None)
    ap.add_argument("--primary-color", default=None,
                    help="Hex or oklch() colour for the tenant's brand.")
    ap.add_argument("--logo-url", default=None)
    ap.add_argument("--native-name", default=None,
                    help="Tenant name in an Indic script if applicable.")

    bootstrap(ap.parse_args())


if __name__ == "__main__":
    main()
