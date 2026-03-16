#!/usr/bin/env python3
"""
Apple Wallet Business Card Generator
Generates a signed .pkpass file for Apple Wallet.
Usage:
    # Generate for a specific person (uses configs/<name>.env):
    python generate_pass.py max-polwin
    python generate_pass.py anna-schmidt
    # Generate for all configs at once:
    python generate_pass.py --all
    # Legacy mode (uses .env in project root):
    python generate_pass.py
Setup:
    1. Shared settings go in .env (certs, team ID, pass type ID)
    2. Per-person settings go in configs/<name>.env
    3. Place certificates in ./certs/
    4. Place icon/logo images in ./assets/
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CONFIGS_DIR = Path("configs")
OUTPUT_DIR = Path("output")


def validate_env_vars(required: list[str]) -> dict[str, str]:
    """Validate that all required environment variables are set."""
    missing: list[str] = []
    values: dict[str, str] = {}
    for var in required:
        val = os.getenv(var)
        if not val:
            missing.append(var)
        else:
            values[var] = val
    if missing:
        logger.error("Missing environment variables: %s", ", ".join(missing))
        logger.error("Copy .env.example to .env and fill in all values.")
        sys.exit(1)
    return values


def validate_files(paths: dict[str, Path]) -> None:
    """Validate that all required files exist."""
    for label, path in paths.items():
        if not path.exists():
            logger.error("Required file missing: %s (%s)", label, path)
            sys.exit(1)
        logger.debug("Found %s: %s", label, path)


def load_config(config_name: str | None = None) -> None:
    """Load shared .env first, then overlay per-person config if given."""
    # Always load shared .env (certs, team ID, etc.)
    load_dotenv(override=False)

    if config_name:
        config_path = CONFIGS_DIR / f"{config_name}.env"
        if not config_path.exists():
            logger.error("Config not found: %s", config_path)
            logger.error("Available configs:")
            for f in sorted(CONFIGS_DIR.glob("*.env")):
                if not f.name.startswith("_"):
                    logger.error("  - %s", f.stem)
            sys.exit(1)
        # Per-person values override shared ones
        load_dotenv(config_path, override=True)
        logger.info("Loaded config: %s", config_path)


def generate_pass(config_name: str | None = None, no_logo: bool = False) -> None:
    """Generate the Apple Wallet .pkpass file."""
    load_config(config_name)

    # --- Validate configuration ---
    env = validate_env_vars([
        "PASS_TYPE_IDENTIFIER",
        "TEAM_IDENTIFIER",
        "ORGANIZATION_NAME",
        "CERT_PATH",
        "KEY_PATH",
        "WWDR_PATH",
        "CONTACT_NAME",
        "CONTACT_TITLE",
        "CONTACT_EMAIL",
        "CONTACT_PHONE",
        "CONTACT_LINKEDIN",
        "LANDING_PAGE_URL",
    ])

    cert_path = Path(env["CERT_PATH"])
    key_path = Path(env["KEY_PATH"])
    wwdr_path = Path(env["WWDR_PATH"])

    validate_files({
        "Certificate": cert_path,
        "Private Key": key_path,
        "WWDR Certificate": wwdr_path,
    })

    # --- Import after validation (fail fast if not installed) ---
    try:
        from py_pkpass.models import Barcode, BarcodeFormat, Generic, Pass
    except ImportError:
        logger.error("py-pkpass not installed. Run: pip install py-pkpass")
        sys.exit(1)

    logger.info("Creating business card pass for %s", env["CONTACT_NAME"])

    # --- Build pass content ---
    card_info = Generic()

    # Auxiliary: Contact details
    card_info.addAuxiliaryField("email", env["CONTACT_EMAIL"], "EMAIL")
    card_info.addAuxiliaryField("phone", env["CONTACT_PHONE"], "PHONE")

    # Back fields: Full details visible when card is flipped
    card_info.addBackField("linkedin", env["CONTACT_LINKEDIN"], "LinkedIn")
    card_info.addBackField("website", env["LANDING_PAGE_URL"], "Website")
    card_info.addBackField(
        "note",
        "Scan the QR code or visit the link above to save my contact.",
        "Info",
    )

    # --- Create Pass object ---
    passfile = Pass(
        card_info,
        passTypeIdentifier=env["PASS_TYPE_IDENTIFIER"],
        organizationName=env["ORGANIZATION_NAME"],
        teamIdentifier=env["TEAM_IDENTIFIER"],
    )

    # Unique serial per person (based on config name or contact name)
    serial_slug = config_name or env["CONTACT_NAME"].lower().replace(" ", "-")
    passfile.serialNumber = f"agradblue-card-{serial_slug}"
    passfile.description = f"Business Card — {env['CONTACT_NAME']}"

    # Colors: match landing page background
    passfile.backgroundColor = "rgb(26, 43, 46)"        # #1A2B2E (same as landing page)
    passfile.foregroundColor = "rgb(255, 255, 255)"     # White text
    passfile.labelColor = "rgb(108, 180, 188)"          # agradblue cadetblue (#6CB4BC)

    # QR Code pointing to landing page
    passfile.barcode = Barcode(
        message=env["LANDING_PAGE_URL"],
        format=BarcodeFormat.QR,
        altText="Scan to save contact",
    )

    # Also set barcodes array (iOS 9+ uses this)
    passfile.barcodes = [
        {
            "message": env["LANDING_PAGE_URL"],
            "format": "PKBarcodeFormatQR",
            "messageEncoding": "iso-8859-1",
            "altText": "Scan to save contact",
        }
    ]

    # --- Add image assets ---
    assets_dir = Path("assets")
    required_images = ["icon.png"]
    if not no_logo:
        required_images.append("logo.png")

    optional_images = [
        "icon@2x.png",
        "icon@3x.png",
        "strip.png",
        "strip@2x.png",
    ]
    if not no_logo:
        optional_images.append("logo@2x.png")

    for img_name in required_images:
        img_path = assets_dir / img_name
        if not img_path.exists():
            logger.error("Required image missing: %s", img_path)
            logger.error(
                "Minimum: icon.png (29x29px) and logo.png (max 160x50px)"
            )
            sys.exit(1)
        with open(img_path, "rb") as f:
            passfile.addFile(img_name, f)
        logger.debug("Added required image: %s", img_name)

    for img_name in optional_images:
        img_path = assets_dir / img_name
        if img_path.exists():
            with open(img_path, "rb") as f:
                passfile.addFile(img_name, f)
            logger.debug("Added optional image: %s", img_name)

    # --- Sign and generate .pkpass ---
    OUTPUT_DIR.mkdir(exist_ok=True)
    name_slug = env["CONTACT_NAME"].lower().replace(" ", "-")
    output_path = OUTPUT_DIR / f"{name_slug}.pkpass"

    logger.info("Signing pass with certificate...")
    try:
        passfile.create(
            str(cert_path),
            str(key_path),
            str(wwdr_path),
            os.getenv("KEY_PASSWORD", ""),
            str(output_path),
        )
    except Exception:
        logger.exception("Failed to create .pkpass file")
        sys.exit(1)

    output_size = output_path.stat().st_size
    logger.info(
        "Successfully created: %s (%.1f KB)", output_path, output_size / 1024
    )
    logger.info("Test: open %s (macOS) or send to iPhone via AirDrop", output_path)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Apple Wallet business card passes",
        epilog="Examples:\n"
               "  python generate_pass.py max-polwin\n"
               "  python generate_pass.py --all\n"
               "  python generate_pass.py  (legacy: uses .env only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "config",
        nargs="?",
        help="Config name from configs/ (e.g. max-polwin)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate passes for all configs in configs/",
    )
    parser.add_argument(
        "--no-logo",
        action="store_true",
        help="Omit the logo image from the pass",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available configs",
    )
    args = parser.parse_args()

    if args.list:
        print("Available configs:")
        for f in sorted(CONFIGS_DIR.glob("*.env")):
            if not f.name.startswith("_"):
                print(f"  {f.stem}")
        return

    if args.all:
        configs = sorted(
            f.stem for f in CONFIGS_DIR.glob("*.env")
            if not f.name.startswith("_")
        )
        if not configs:
            logger.error("No configs found in %s/", CONFIGS_DIR)
            sys.exit(1)
        logger.info("Generating passes for %d configs...", len(configs))
        for name in configs:
            generate_pass(name, no_logo=args.no_logo)
        logger.info("Done! All passes in %s/", OUTPUT_DIR)
    elif args.config:
        generate_pass(args.config, no_logo=args.no_logo)
    else:
        # Legacy mode: just use .env
        generate_pass(no_logo=args.no_logo)


if __name__ == "__main__":
    main()
