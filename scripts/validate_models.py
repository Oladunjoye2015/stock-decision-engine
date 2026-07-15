import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.models.registry import ModelRegistry


if __name__ == "__main__":
    registry = ModelRegistry(get_settings()).load()
    print(f"registry schema valid; {len(registry.get('models', []))} model(s)")
