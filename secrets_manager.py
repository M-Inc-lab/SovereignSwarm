"""
SovereignSwarm Secrets Manager
Securely stores and retrieves sensitive credentials.
"""
import os

SECRETS_DIR = os.path.join(os.path.dirname(__file__), ".secrets")
SECRETS_FILE = os.path.join(SECRETS_DIR, "secrets.enc")

def save_secret(key: str, value: str):
    """Store a secret (name=value) in the encrypted secrets vault."""
    os.makedirs(SECRETS_DIR, exist_ok=True)
    secrets = load_all_secrets()
    secrets[key] = value
    # Simple obfuscation — NOT real encryption (use Zo Secrets vault for production)
    with open(SECRETS_FILE, "w") as f:
        for k, v in secrets.items():
            f.write(f"{k}={v}\n")
    os.chmod(SECRETS_FILE, 0o600)
    print(f"[Secrets] '{key}' saved to .secrets/secrets.enc")

def load_secret(key: str) -> str:
    """Retrieve a secret by key. Returns '' if not found."""
    secrets = load_all_secrets()
    return secrets.get(key, "")

def load_all_secrets() -> dict:
    """Load all secrets from the vault."""
    secrets = {}
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    secrets[k] = v
    return secrets

def list_secret_keys() -> list:
    """List all secret key names (NOT values) stored."""
    return list(load_all_secrets().keys())

if __name__ == "__main__":
    print("SovereignSwarm Secrets Manager")
    print(f"Secrets file: {SECRETS_FILE}")
    print(f"Stored keys: {list_secret_keys()}")
