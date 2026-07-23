#!/usr/bin/env python3
import os
import shutil
import sys
import time
from pathlib import Path


def _seed_bundled_models() -> None:
    """Salin model yang sudah dibundel dalam image (/opt/models) ke U2NET_HOME
    agar rembg tidak perlu mengunduh dari internet saat runtime. Berguna bila
    VPS tidak dapat menjangkau GitHub tempat rembg mengunduh model."""
    src = Path("/opt/models")
    if not src.is_dir():
        return
    home = Path(os.getenv("U2NET_HOME", "/models"))
    home.mkdir(parents=True, exist_ok=True)
    for bundled in src.glob("*.onnx"):
        target = home / bundled.name
        if not target.exists():
            shutil.copy2(bundled, target)
            print(f"Model {bundled.stem} disalin dari bundel image ke {target}.")


def main() -> int:
    from rembg import new_session

    _seed_bundled_models()

    models = [name.strip() for name in os.getenv("PRELOAD_MODELS", "u2netp").split(",") if name.strip()]
    allowed = set(os.getenv("ALLOWED_REMBG_MODELS", "u2netp,isnet-general-use").split(","))
    for model in models:
        if model not in allowed:
            print(f"Model tidak diizinkan: {model}", file=sys.stderr)
            return 2
        for attempt in range(1, 4):
            try:
                print(f"Menyiapkan model {model} (percobaan {attempt}/3)")
                new_session(model)
                print(f"Model {model} siap.")
                break
            except Exception as exc:
                if attempt == 3:
                    print(f"Model {model} gagal disiapkan: {type(exc).__name__}", file=sys.stderr)
                    return 1
                time.sleep(2**attempt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
