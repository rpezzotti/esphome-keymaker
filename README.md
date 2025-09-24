# ESPHome Keymaker

Deterministic generator for **ESPHome API encryption keys** and **OTA passwords**.  
This repo gives you two tools:

- `esphome_keys` — a Python module that derives keys/passwords from a single **master secret** using HMAC-SHA256.
- `gen_secrets.py` — a CLI script that scans your ESPHome YAML files, finds device names + substitution variables, and generates a consistent `secrets.yaml`.

With this, you can:
- Have **unique API keys per device** (blast-radius limited).
- Generate **per-device OTA passwords** (or keep tiers).
- Recreate secrets deterministically from one master secret.
- Avoid spreadsheets of secrets or insecure key reuse.

---

## Installation

Clone this repo and install dependencies:

```bash
git clone https://github.com/rpezzotti/esphome-keymaker.git
cd esphome-keymaker
pip install pyyaml
```

---

## Usage

### 1. Prepare a master secret
Pick a strong 32-byte base64 string and store it securely. (message for myself: IF YOU LOSE THIS YOU CANNOT RECREATE EVERYTHING... SO PUT IT IN YOUR PASSWORD MANAGER AND DO NOT COMMIT IT FFS)

```bash
# Option A: environment variable
export ESPHOME_MASTER_SECRET="$(openssl rand -base64 32)"

# Option B: file
openssl rand -base64 32 > ~/.esph_master
chmod 600 ~/.esph_master
```


### 2. Reference device name in your ESPHome YAML
`gen_secrets.py` no longer accepts a `--variable` flag. Instead it deterministically creates secret keys named `<mode>_<device_name>` (for example `api_switch_living` or `ota_switch_living`). Device names are taken (in this order) from `substitutions.name`, `substitutions.device_name`, then `esphome.name`, then the filename stem.

If you previously stored secret key names in substitutions (for example `api_secret: api_key_switch_living`), those values are ignored by the current script. YAML `!secret` tags are supported and will be parsed as the underlying scalar (see Notes).

Example device YAML (only the device name is needed):

```yaml
substitutions:
  name: switch_living          # preferred device name
```

Device name precedence when scanning a file is:
1. `substitutions.name` or `substitutions.device_name` (checked in that order)
2. `esphome.name`
3. filename stem

### 3. Generate API keys
```bash
python gen_secrets.py ./esphome/devices --mode api --master-secret-file ~/.esph_master --output ./esphome/secrets.yaml
```

The script derives deterministic values (via `esphome_keys`) and merges any new secrets into `./esphome/secrets.yaml`. 

### 4. Generate OTA passwords
```bash
python gen_secrets.py ./esphome/devices --mode ota --master-secret-file ~/.esph_master --print
```

This prints per-device OTA secrets to stdout, so you can paste/append manually.

---

## Example Workflow

1. Add devices with `substitutions.name` (or `substitutions.device_name`), and a substitution for `api_secret` / `ota_secret` holding the secret key name.
2. Run `gen_secrets.py` to populate/update `secrets.yaml`.
3. Build and flash as usual with `esphome run`.
4. If you lose `secrets.yaml`, just re-generate with the same master secret — values will be identical.

---

## Module API

You can also import the module directly:

```python
from esphome_keys import derive_api_key, derive_ota_password

master_secret = "super-secret-string"

api_key = derive_api_key("switch_living", master_secret)
ota_pw = derive_ota_password("switch_living", master_secret)
```

---

## Notes

- YAML `!secret` support: `gen_secrets.py` registers a constructor with PyYAML's SafeLoader so common ESPHome `!secret` tags are parsed as their underlying scalar names (e.g. `!secret ota_pass` -> `ota_pass`). You don't need to preprocess files to remove `!secret` tags.
-- Key naming: the script writes keys named `<mode>_<device_name>` (for example `api_switch_living`). It no longer reads a user-specified substitution variable.

---

## Security Notes

- Keep your **master secret** safe (password manager, encrypted file). Anyone with it can regenerate all keys.
- `secrets.yaml` should **not** be committed to Git in plaintext. Use [sops](https://github.com/getsops/sops) or `ansible-vault` if you must version it.
- Rotate selectively: if one device is compromised, just regenerate its key.

---

## License

MIT License

```
MIT License

Copyright (c) 2025 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Roadmap

- Support CSV/JSON inventory for bulk generation with VLAN/risk metadata.
- Optional split output (API vs OTA secrets).
- Pre-commit hook to auto-refresh secrets.

---
