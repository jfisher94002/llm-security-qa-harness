#!/usr/bin/env python3
"""
LLM-03 Tier 2: Asset Identity Layer.

Verifies the SHA-256 hash of a local artifact against the approved release
manifest and, when configured, verifies an Ed25519 detached signature with the
maintained Python cryptography library.

Exit codes:
    0 = passed
    1 = human review required
    2 = deterministic hard block
    3 = invalid configuration or tool failure
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


EXIT_PASS = 0
EXIT_REVIEW = 1
EXIT_HARD_BLOCK = 2
EXIT_INVALID = 3


class SignatureConfigurationError(ValueError):
    """Raised when signature verification cannot be attempted safely."""


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def compute_sha256(file_path, chunk_size=65536):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def find_manifest_entry(manifest, file_name):
    for entry in manifest.get("models", []):
        if entry.get("file_name") == file_name:
            return entry
    return None


def read_hex_file(path, label):
    try:
        with open(path, encoding="utf-8") as handle:
            return bytes.fromhex("".join(handle.read().split()))
    except ValueError as exc:
        raise SignatureConfigurationError(f"{label} is not valid hex: {exc}") from None


def load_cryptography_verifier():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise SignatureConfigurationError(
            "cryptography is required for Ed25519 verification. "
            "Install it with: python3 -m pip install -r requirements.txt"
        ) from exc
    return Ed25519PublicKey, InvalidSignature


def verify_ed25519(public_key, signature, message):
    Ed25519PublicKey, InvalidSignature = load_cryptography_verifier()
    if len(public_key) != 32:
        raise SignatureConfigurationError("Ed25519 public key must be 32 bytes")
    if len(signature) != 64:
        raise SignatureConfigurationError("Ed25519 signature must be 64 bytes")
    try:
        key = Ed25519PublicKey.from_public_bytes(public_key)
    except ValueError as exc:
        raise SignatureConfigurationError(f"malformed Ed25519 public key: {exc}") from None
    try:
        key.verify(signature, message)
    except InvalidSignature:
        return False
    return True


def resolve_signature_config(args, entry):
    signature_file = args.signature_file or entry.get("signature_file")
    public_key_file = args.public_key_file or entry.get("public_key_file")
    public_key_hex = args.public_key_hex or entry.get("ed25519_public_key")
    return signature_file, public_key_file, public_key_hex


def invalid_artifact(args, out_path, result, message, extra=None):
    artifact = {
        "check": "asset_identity",
        "result": result,
        "exit_code": EXIT_INVALID,
        "timestamp": now_utc(),
        "model_file": args.model_file,
        "manifest": args.manifest,
        "error": message,
    }
    if extra:
        artifact.update(extra)
    write_json(out_path, artifact)
    print(f"ERROR — {message}")
    sys.exit(EXIT_INVALID)


def main():
    parser = argparse.ArgumentParser(description="LLM-03 Tier 2: Asset identity check")
    parser.add_argument("--model-file", required=True, help="Path to local artifact to verify")
    parser.add_argument("--manifest", default="llm03/release_manifest.json", help="Path to release manifest")
    parser.add_argument("--output", default="llm03/sample_outputs/tier2", help="Output directory for artifacts")
    parser.add_argument("--signature-file", help="Detached Ed25519 signature file in hex")
    parser.add_argument("--public-key-file", help="Ed25519 public key file in hex")
    parser.add_argument("--public-key-hex", help="Ed25519 public key as hex")
    args = parser.parse_args()

    print("=" * 60)
    print("LLM-03 Tier 2: Asset Identity Layer")
    print("=" * 60)

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "hash_check.json")

    if not os.path.exists(args.model_file):
        invalid_artifact(args, out_path, "INVALID_MODEL_FILE", "model file not found")
    if not os.path.exists(args.manifest):
        invalid_artifact(args, out_path, "INVALID_MANIFEST", "manifest not found")

    try:
        manifest = load_manifest(args.manifest)
    except json.JSONDecodeError as exc:
        invalid_artifact(args, out_path, "INVALID_MANIFEST_JSON", f"manifest JSON is invalid: {exc}")

    file_name = os.path.basename(args.model_file)
    file_size = os.path.getsize(args.model_file)
    actual_hash = compute_sha256(args.model_file)
    entry = find_manifest_entry(manifest, file_name)

    artifact = {
        "check": "asset_identity",
        "tool": "hashlib sha256 + cryptography Ed25519 verification",
        "timestamp": now_utc(),
        "model_file": args.model_file,
        "file_name": file_name,
        "file_size_bytes": file_size,
        "actual_hash": actual_hash,
        "expected_hash": entry.get("sha256") if entry else None,
        "manifest_entry_found": entry is not None,
        "hash_match": False,
        "signature": {
            "configured": False,
            "verified": None,
            "signature_file": None,
            "public_key_source": None,
        },
    }

    if not entry:
        artifact["result"] = "HARD_BLOCK_NO_MANIFEST_ENTRY"
        artifact["exit_code"] = EXIT_HARD_BLOCK
        write_json(out_path, artifact)
        print(f"FAIL — No manifest entry found for: {file_name}")
        sys.exit(EXIT_HARD_BLOCK)

    expected_hash = entry.get("sha256", "")
    if expected_hash == "REPLACE_WITH_ACTUAL_SHA256_HASH" or not expected_hash:
        artifact["result"] = "INVALID_PLACEHOLDER_HASH"
        artifact["exit_code"] = EXIT_INVALID
        write_json(out_path, artifact)
        print(f"ERROR — Manifest entry for {file_name} does not contain a real hash.")
        sys.exit(EXIT_INVALID)

    if actual_hash != expected_hash:
        artifact["result"] = "HARD_BLOCK_HASH_MISMATCH"
        artifact["exit_code"] = EXIT_HARD_BLOCK
        write_json(out_path, artifact)
        print("FAIL — Hash mismatch.")
        print(f"  Expected: {expected_hash}")
        print(f"  Actual:   {actual_hash}")
        sys.exit(EXIT_HARD_BLOCK)

    artifact["hash_match"] = True
    signature_file, public_key_file, public_key_hex = resolve_signature_config(args, entry)

    signature_config_values = [bool(signature_file), bool(public_key_file or public_key_hex)]
    if any(signature_config_values) and not all(signature_config_values):
        artifact["result"] = "INVALID_SIGNATURE_CONFIGURATION"
        artifact["exit_code"] = EXIT_INVALID
        write_json(out_path, artifact)
        print("ERROR — Signature verification needs both a signature and a public key.")
        sys.exit(EXIT_INVALID)

    if signature_file and (public_key_file or public_key_hex):
        artifact["signature"].update({
            "configured": True,
            "verified": None,
            "signature_file": signature_file,
            "public_key_source": public_key_file or "manifest",
        })
        try:
            signature = read_hex_file(signature_file, "signature")
            if public_key_file:
                public_key = read_hex_file(public_key_file, "public key")
                public_key_source = public_key_file
            else:
                try:
                    public_key = bytes.fromhex("".join(public_key_hex.split()))
                except ValueError as exc:
                    raise SignatureConfigurationError(f"public key is not valid hex: {exc}") from None
                public_key_source = "manifest"
            with open(args.model_file, "rb") as handle:
                message = handle.read()
            verified = verify_ed25519(public_key, signature, message)
        except (OSError, SignatureConfigurationError) as exc:
            artifact["result"] = "INVALID_SIGNATURE_CONFIGURATION"
            artifact["exit_code"] = EXIT_INVALID
            artifact["signature"]["error"] = str(exc)
            write_json(out_path, artifact)
            print(f"ERROR — Signature verification could not run: {exc}")
            sys.exit(EXIT_INVALID)

        artifact["signature"].update({
            "verified": verified,
            "public_key_source": public_key_source,
        })
        if not verified:
            artifact["result"] = "HARD_BLOCK_SIGNATURE_FAILURE"
            artifact["exit_code"] = EXIT_HARD_BLOCK
            write_json(out_path, artifact)
            print("FAIL — Ed25519 signature verification failed.")
            sys.exit(EXIT_HARD_BLOCK)

    artifact["result"] = "PASS"
    artifact["exit_code"] = EXIT_PASS
    write_json(out_path, artifact)
    print("PASS — Artifact identity verified.")
    print(f"Artifact: {out_path}")
    sys.exit(EXIT_PASS)


if __name__ == "__main__":
    main()
