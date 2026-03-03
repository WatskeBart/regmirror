#!/usr/bin/env python3
"""
regmirror.py — Download container images to OCI tarballs and re-upload
them to a private registry with domain rewriting.

Usage:
    # Download all images listed in images.txt to ./tarballs/
    ./regmirror.py download -f images.txt -o ./tarballs

    # Upload all tarballs to a private registry
    ./regmirror.py upload -d ./tarballs -r my.registry.tld

    # Download and upload in one go
    ./regmirror.py sync -f images.txt -o ./tarballs -r my.registry.tld

Requires: skopeo (https://github.com/containers/skopeo)

The manifest.json file maps filenames to original image references,
making the conversion fully reversible without fragile filename encoding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Author / version
# ---------------------------------------------------------------------------
__version__ = "1.2.0"
__author__ = "WatskeBart"
__description__ = "regmirror — mirror container images via OCI tarballs"

# ---------------------------------------------------------------------------
# Colored logging
# ---------------------------------------------------------------------------
class _ColorFormatter(logging.Formatter):
    _LEVEL_COLORS = {
        logging.DEBUG:    "\033[36m",    # cyan
        logging.INFO:     "\033[32m",    # green
        logging.WARNING:  "\033[33m",    # yellow
        logging.ERROR:    "\033[31m",    # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    _DIM   = "\033[2m"
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._LEVEL_COLORS.get(record.levelno, "")
        record = logging.makeLogRecord(record.__dict__)  # don't mutate original
        record.asctime   = f"{self._DIM}{self.formatTime(record, self.datefmt)}{self._RESET}"
        record.levelname = f"{color}{record.levelname}{self._RESET}"
        record.msg       = f"{color}{record.getMessage()}{self._RESET}"
        record.args      = None  # already interpolated above
        return f"{record.asctime} [{record.levelname}] {record.msg}"


def _setup_logging() -> None:
    handler = logging.StreamHandler()
    if sys.stderr.isatty():
        handler.setFormatter(_ColorFormatter(datefmt="%H:%M:%S"))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


_setup_logging()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex for parsing image references
# ---------------------------------------------------------------------------
IMAGE_RE = re.compile(
    r"^(?P<registry>([\w.\-]+\.[\w.\-]+(:\d+)?|[\w.\-]+:\d+)(?=/[a-z0-9._-]+))?"
    r"(?:/?)(?P<image>[a-z0-9._-]+(/[a-z0-9._-]+)*)"
    r"(?::(?P<tag>[\w.\-]{1,127})|@(?P<digest>sha256:[a-fA-F0-9]{64}))?$",
    re.IGNORECASE,
)

MANIFEST_FILE = "manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_image_ref(ref: str) -> dict:
    """Parse an image reference into its components."""
    ref = ref.strip()
    m = IMAGE_RE.match(ref)
    if not m:
        raise ValueError(f"Cannot parse image reference: {ref}")
    digest = m.group("digest")
    return {
        "registry": m.group("registry") or "docker.io",
        "image": m.group("image"),
        "tag": m.group("tag") or (None if digest else "latest"),
        "digest": digest,
        "original": ref,
    }


def ref_to_filename(ref: str) -> str:
    """
    Convert an image reference to a safe filename.
    Uses a simple scheme: replace / with _ and : with -
    The manifest.json provides the authoritative reverse mapping.
    """
    name = ref.replace("://", "")
    # Handle @sha256: digests — keep only first 12 chars of hash
    if "@sha256:" in name:
        base, digest = name.split("@sha256:")
        name = f"{base}@sha256-{digest[:12]}"
    name = name.replace("/", "_").replace(":", "-")
    return f"{name}.tar"


def rewrite_for_registry(parsed: dict, target_registry: str) -> str:
    """
    Rewrite an image reference for a private registry.

    docker.io/library/nginx:1.25  → my.registry.tld/dockerio/library/nginx:1.25
    gcr.io/project/app:v1         → my.registry.tld/gcrio/project/app:v1
    """
    # Flatten source registry into a path component (remove dots and colons)
    source = parsed["registry"]
    registry_path = source.replace(".", "").replace(":", "")

    image = parsed["image"]
    tag_or_digest = ""
    if parsed["digest"]:
        tag_or_digest = f"@{parsed['digest']}"
    elif parsed["tag"]:
        tag_or_digest = f":{parsed['tag']}"
    else:
        tag_or_digest = ":latest"

    return f"{target_registry}/{registry_path}/{image}{tag_or_digest}"


def load_manifest(output_dir: Path) -> dict:
    """Load or create the manifest file."""
    manifest_path = output_dir / MANIFEST_FILE
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    return {}


def save_manifest(output_dir: Path, manifest: dict) -> None:
    """Save the manifest file."""
    manifest_path = output_dir / MANIFEST_FILE
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


class RemoteInfo(NamedTuple):
    digest: str | None
    has_embedded_signatures: bool


def inspect_remote(ref: str, args: argparse.Namespace) -> RemoteInfo:
    """
    Fetch the raw manifest for a remote image via skopeo inspect --raw.

    Returns:
      - digest: sha256 of the raw manifest bytes (equivalent to the registry's
        Docker-Content-Digest header), or None on failure.
      - has_embedded_signatures: True when the manifest JSON contains a
        'signatures' key (old-style Docker Content Trust / Notary v1 signing).
        Modern cosign/sigstore signatures are stored as separate OCI artifacts
        and are NOT detected here — skopeo copy handles them independently.

    A single network call provides both pieces of information.
    """
    cmd = ["skopeo", "inspect", "--raw"]
    if getattr(args, "src_tls_verify", None) is not None:
        cmd.append(f"--tls-verify={'true' if args.src_tls_verify else 'false'}")
    if getattr(args, "src_creds", None):
        cmd += ["--creds", args.src_creds]
    if getattr(args, "authfile", None):
        cmd += ["--authfile", args.authfile]
    cmd.append(f"docker://{ref}")
    log.debug("Inspecting remote manifest: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, check=True, capture_output=True)
        raw = result.stdout
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        has_sigs = bool(json.loads(raw).get("signatures"))
        return RemoteInfo(digest=digest, has_embedded_signatures=has_sigs)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return RemoteInfo(digest=None, has_embedded_signatures=False)


def run_skopeo(args: list[str], dry_run: bool = False) -> bool:
    """Run a skopeo command, return True on success."""
    cmd = ["skopeo"] + args
    log.info("Running: %s", " ".join(cmd))
    if dry_run:
        log.info("[DRY RUN] Would execute above command")
        return True
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error("skopeo failed (exit code %d)", e.returncode)
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_download(args: argparse.Namespace) -> int:
    """Download images listed in a file to OCI tarballs."""
    images_file = Path(args.file)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not images_file.exists():
        log.error("Images file not found: %s", images_file.resolve())
        return 1

    refs = [
        line.strip()
        for line in images_file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not refs:
        log.warning("No images found in %s", images_file)
        return 1

    log.info("Downloading %d image(s) to %s", len(refs), output_dir)

    manifest = load_manifest(output_dir)
    errors = 0
    skipped = 0

    for ref in refs:
        try:
            parsed = parse_image_ref(ref)
        except ValueError as e:
            log.error("%s", e)
            errors += 1
            continue

        filename = ref_to_filename(ref)
        tarball = output_dir / filename

        remote_info: RemoteInfo | None = None
        needs_download = True

        if tarball.exists() and not args.force:
            if parsed["digest"]:
                # Digest-pinned refs are immutable — the content can never change.
                log.info("Skipping (digest-pinned): %s → %s", ref, filename)
                skipped += 1
                needs_download = False
            else:
                # Tag-based ref: inspect the remote manifest to get digest + signature info.
                stored_digest = manifest.get(filename, {}).get("digest")
                remote_info = inspect_remote(ref, args)
                if remote_info.digest is None:
                    log.warning(
                        "Could not fetch remote digest for %s — skipping (use --force to re-download anyway)",
                        ref,
                    )
                    skipped += 1
                    needs_download = False
                elif remote_info.digest == stored_digest:
                    log.info("Skipping (up to date): %s → %s", ref, filename)
                    skipped += 1
                    needs_download = False
                else:
                    log.info(
                        "Tag %s points to a newer image (stored: %s, remote: %s) — re-downloading",
                        ref,
                        stored_digest[:19] if stored_digest else "none",
                        remote_info.digest[:19],
                    )

        if needs_download:
            # Inspect the remote manifest if we haven't already (first download or --force).
            if remote_info is None and not parsed["digest"]:
                remote_info = inspect_remote(ref, args)

            log.info("Downloading: %s → %s", ref, filename)
            src = f"docker://{ref}"
            dst = f"oci-archive:{tarball}"

            skopeo_args = ["copy"]
            if args.src_tls_verify is not None:
                skopeo_args.append(f"--src-tls-verify={'true' if args.src_tls_verify else 'false'}")
            if args.src_creds:
                skopeo_args += ["--src-creds", args.src_creds]
            if getattr(args, "authfile", None):
                skopeo_args += ["--src-authfile", args.authfile]

            # Auto-detect embedded signatures; also honour the explicit --remove-signatures flag.
            auto_remove = remote_info is not None and remote_info.has_embedded_signatures
            if auto_remove and not getattr(args, "remove_signatures", False):
                log.info("Embedded signatures detected in %s — stripping automatically", ref)
            if getattr(args, "remove_signatures", False) or auto_remove:
                skopeo_args.append("--remove-signatures")

            skopeo_args += [src, dst]

            if not run_skopeo(skopeo_args, dry_run=args.dry_run):
                errors += 1
                continue

        # Update manifest, preserving any previously-stored digest if we have nothing better.
        resolved_digest = (remote_info.digest if remote_info else None) or parsed["digest"]
        manifest[filename] = {
            "original": ref,
            "registry": parsed["registry"],
            "image": parsed["image"],
            "tag": parsed["tag"],
            "digest": resolved_digest or manifest.get(filename, {}).get("digest"),
        }

    save_manifest(output_dir, manifest)
    log.info(
        "Done. %d downloaded, %d skipped, %d errors. Manifest: %s",
        len(refs) - errors - skipped,
        skipped,
        errors,
        output_dir / MANIFEST_FILE,
    )
    return 1 if errors else 0


def cmd_upload(args: argparse.Namespace) -> int:
    """Upload tarballs to a private registry with domain rewriting."""
    tarball_dir = Path(args.dir)
    target_registry = args.registry.rstrip("/")

    manifest = load_manifest(tarball_dir)
    if not manifest:
        log.error("No manifest.json found in %s. Run 'download' first.", tarball_dir)
        return 1

    log.info(
        "Uploading %d image(s) to %s", len(manifest), target_registry
    )

    errors = 0
    for filename, meta in manifest.items():
        tarball = tarball_dir / filename
        if not tarball.exists():
            log.warning("Tarball not found, skipping: %s", filename)
            errors += 1
            continue

        target_ref = rewrite_for_registry(meta, target_registry)
        log.info("Uploading: %s → %s", filename, target_ref)

        src = f"oci-archive:{tarball}"
        dst = f"docker://{target_ref}"

        skopeo_args = ["copy"]
        if args.dest_tls_verify is not None:
            skopeo_args.append(f"--dest-tls-verify={'true' if args.dest_tls_verify else 'false'}")
        if args.dest_creds:
            skopeo_args += ["--dest-creds", args.dest_creds]
        if getattr(args, "authfile", None):
            skopeo_args += ["--dest-authfile", args.authfile]
        if getattr(args, "remove_signatures", False):
            skopeo_args.append("--remove-signatures")
        skopeo_args += [src, dst]

        if not run_skopeo(skopeo_args, dry_run=args.dry_run):
            errors += 1

    log.info("Done. %d uploaded, %d errors.", len(manifest) - errors, errors)
    return 1 if errors else 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Download + upload in one go."""
    ret = cmd_download(args)
    if ret != 0 and not args.continue_on_error:
        log.error("Download had errors, aborting upload. Use --continue-on-error to proceed.")
        return ret
    args.dir = args.output  # upload reads from --dir
    return cmd_upload(args)


def cmd_list(args: argparse.Namespace) -> int:
    """List manifest contents and show what the upload targets would be."""
    tarball_dir = Path(args.dir)
    manifest = load_manifest(tarball_dir)
    if not manifest:
        log.error("No manifest.json found in %s", tarball_dir)
        return 1

    target_registry = args.registry

    print(f"{'Filename':<55} {'Original':<45} {'Upload Target'}")
    print("-" * 150)
    for filename, meta in manifest.items():
        original = meta["original"]
        target = rewrite_for_registry(meta, target_registry) if target_registry else "—"
        print(f"{filename:<55} {original:<45} {target}")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mirror container images via OCI tarballs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__} — {__description__}"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without executing"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- download --
    dl = sub.add_parser("download", help="Download images to tarballs")
    dl.add_argument("-f", "--file", required=True, help="Text file with image refs")
    dl.add_argument("-o", "--output", default="./tarballs", help="Output directory")
    dl.add_argument("--force", action="store_true", help="Re-download existing tarballs")
    dl.add_argument(
        "--src-tls-verify",
        default=None,
        type=lambda x: x.lower() not in ("false", "0", "no"),
        dest="src_tls_verify",
        metavar="BOOL",
        help="TLS verification for source registry (e.g. --src-tls-verify=false)",
    )
    dl.add_argument(
        "--src-creds", default=None, metavar="USER:PASS",
        help="Credentials for source registry",
    )
    dl.add_argument(
        "--authfile", default=None, metavar="FILE",
        help="Path to auth.json for authenticating to source registry",
    )
    dl.add_argument(
        "--remove-signatures", action="store_true", dest="remove_signatures",
        help="Strip image signatures (avoids errors when saving to oci-archive)",
    )

    # -- upload --
    ul = sub.add_parser("upload", help="Upload tarballs to a registry")
    ul.add_argument("-d", "--dir", default="./tarballs", help="Tarball directory")
    ul.add_argument("-r", "--registry", required=True, help="Target registry URL")
    ul.add_argument(
        "--dest-tls-verify",
        default=None,
        type=lambda x: x.lower() not in ("false", "0", "no"),
        dest="dest_tls_verify",
        metavar="BOOL",
        help="TLS verification for destination registry (e.g. --dest-tls-verify=false)",
    )
    ul.add_argument(
        "--dest-creds", default=None, metavar="USER:PASS",
        help="Credentials for destination registry",
    )
    ul.add_argument(
        "--authfile", default=None, metavar="FILE",
        help="Path to auth.json for authenticating to destination registry",
    )
    ul.add_argument(
        "--remove-signatures", action="store_true", dest="remove_signatures",
        help="Strip image signatures (avoids errors when pushing to a registry)",
    )

    # -- sync --
    sy = sub.add_parser("sync", help="Download + upload in one step")
    sy.add_argument("-f", "--file", required=True, help="Text file with image refs")
    sy.add_argument("-o", "--output", default="./tarballs", help="Output directory")
    sy.add_argument("-r", "--registry", required=True, help="Target registry URL")
    sy.add_argument("--force", action="store_true", help="Re-download existing tarballs")
    sy.add_argument(
        "--continue-on-error", action="store_true", dest="continue_on_error",
        help="Continue with upload even if some downloads failed",
    )
    sy.add_argument(
        "--src-tls-verify", default=None, dest="src_tls_verify", metavar="BOOL",
        type=lambda x: x.lower() not in ("false", "0", "no"),
    )
    sy.add_argument(
        "--dest-tls-verify", default=None, dest="dest_tls_verify", metavar="BOOL",
        type=lambda x: x.lower() not in ("false", "0", "no"),
    )
    sy.add_argument("--src-creds", default=None, metavar="USER:PASS",
                    help="Credentials for source registry")
    sy.add_argument("--dest-creds", default=None, metavar="USER:PASS",
                    help="Credentials for destination registry")
    sy.add_argument(
        "--authfile", default=None, metavar="FILE",
        help="Path to auth.json used for both source and destination registries",
    )
    sy.add_argument(
        "--remove-signatures", action="store_true", dest="remove_signatures",
        help="Strip image signatures during copy",
    )

    # -- list --
    ls = sub.add_parser("list", help="Show manifest and upload targets")
    ls.add_argument("-d", "--dir", default="./tarballs", help="Tarball directory")
    ls.add_argument("-r", "--registry", default=None, help="Preview upload targets")

    args = parser.parse_args()
    commands = {
        "download": cmd_download,
        "upload": cmd_upload,
        "sync": cmd_sync,
        "list": cmd_list,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
        sys.exit(130)
