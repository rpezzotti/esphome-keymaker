"""
Scan a folder for ESPHome YAMLs and generate secrets entries.

Examples:
  python gen_secrets.py ./esphome/devices --variable api_secret --master-secret-file ~/.esph_master --output ./esphome/secrets.yaml
  python gen_secrets.py ./esphome/devices --variable ota_secret  --master-secret "paste-super-secret" --print

Behavior:
- Recursively scans *.yml, *.yaml
- Device name precedence: substitutions.name > esphome.name > filename stem
- Looks up the given --variable in 'substitutions' (e.g. 'api_secret' -> 'api_key_switch_living')
- If --mode api: writes that key with derive_api_key(device_name)
- If --mode ota:  writes that key with derive_ota_password(device_name)
- Merges into secrets.yaml; does not overwrite existing keys unless --force
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from typing import Dict, Tuple, Optional

import yaml  # pip install pyyaml

# register a constructor so SafeLoader can handle ESPHome '!secret' tags
def _construct_secret(loader, node):
    # Return the underlying scalar (e.g. "!secret ota_pass" -> "ota_pass")
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None

yaml.SafeLoader.add_constructor("!secret", _construct_secret)

# local module
from esphome_keys import derive_api_key, derive_ota_password

YAML_EXTS = {".yml", ".yaml"}

def load_master_secret(args: argparse.Namespace) -> str:
    if args.master_secret:
        return args.master_secret
    if args.master_secret_file:
        p = Path(os.path.expanduser(args.master_secret_file))
        if not p.exists():
            sys.exit(f"Master secret file not found: {p}")
        return p.read_text().strip()
    # Also allow environment variable
    env = os.getenv("ESPHOME_MASTER_SECRET")
    if env:
        return env.strip()
    sys.exit("Missing master secret. Use --master-secret, --master-secret-file, or ESPHOME_MASTER_SECRET env var.")

def read_yaml(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[WARN] Failed to parse YAML: {path} ({e})", file=sys.stderr)
        return {}

def find_device_identity(doc: Dict, path: Path) -> Tuple[str, Optional[Dict]]:
    """
    Returns (device_name, substitutions_dict_or_None)
    """
    # name precedence
    name = None
    #checks for name or device_name in substitutions first, then for name esphome, then filename
    subs = doc.get("substitutions") if isinstance(doc, dict) else None

    if isinstance(subs, dict):
        name = subs.get("name")
        name = subs.get("device_name") if not name else name
    if not name:
        esphome = doc.get("esphome") if isinstance(doc, dict) else None
        if isinstance(esphome, dict):
            name = esphome.get("name")
    if not name:
        name = path.stem
    return str(name), (subs if isinstance(subs, dict) else None)

def walk_yaml_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in YAML_EXTS:
            yield p

def load_existing_secrets(path: Optional[Path]) -> Dict[str, str]:
    if not path or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            print(f"[WARN] secrets file is not a mapping, ignoring: {path}", file=sys.stderr)
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        print(f"[WARN] Failed to read secrets: {path} ({e})", file=sys.stderr)
        return {}

def write_secrets(path: Path, mapping: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(mapping, f, default_flow_style=False, sort_keys=True, allow_unicode=True)

def main():
    ap = argparse.ArgumentParser(description="Generate ESPHome secrets for devices in a folder.")
    ap.add_argument("folder", help="Folder containing ESPHome YAMLs (recursively scanned)")
    ap.add_argument("--mode", choices=["api", "ota"], default="api",
                    help="Type of secret to derive (default: api)")
    ap.add_argument("--master-secret", help="Master secret (string) for deterministic derivation")
    ap.add_argument("--master-secret-file", help="Path to file containing master secret")
    ap.add_argument("--output", help="Path to secrets.yaml to create/update")
    ap.add_argument("--print", action="store_true", help="Print resulting key: value pairs instead of writing a file")
    args = ap.parse_args()

    root = Path(args.folder).resolve()
    if not root.exists():
        sys.exit(f"Folder not found: {root}")

    master_secret = load_master_secret(args)

    # Load existing secrets (to merge)
    secrets_path = Path(args.output).resolve() if args.output else None
    existing = load_existing_secrets(secrets_path)

    new_kv: Dict[str, str] = {}
    seen_devices = set()

    for yml in walk_yaml_files(root):
        doc = read_yaml(yml)
        if not isinstance(doc, dict):
            continue

        device_name, subs = find_device_identity(doc, yml)
        seen_devices.add(device_name)
        secret_key_name = args.mode + "-" + str(device_name).strip()

        # Skip if exists and not forcing
        if secret_key_name in existing:
            # Already present—don’t overwrite
            print(f"[INFO] Skipping existing key '{secret_key_name}'")
            continue

        if args.mode == "api":
            secret_value = derive_api_key(device_name, master_secret)
        else:
            secret_value = derive_ota_password(device_name, master_secret)

        new_kv[secret_key_name] = secret_value

    # Merge maps (existing wins unless --force)
    out_map = dict(existing)
    out_map.update(new_kv)

    if args.print or not secrets_path:
        # Print only newly generated keys (nice for piping >>)
        for k, v in new_kv.items():
            print(f'{k}: "{v}"')
    else:
        write_secrets(secrets_path, out_map)
        print(f"[OK] Updated {secrets_path} with {len(new_kv)} new key(s). Skipped existing: {len(existing) - len(set(new_kv).intersection(existing.keys()))}")

if __name__ == "__main__":
    main()