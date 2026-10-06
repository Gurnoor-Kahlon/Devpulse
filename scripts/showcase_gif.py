"""Assemble real browser frames; no metric/DOM edits.

Optional local tool setup (does not affect application locks or runtime images):
  .venv/bin/python -m pip install --target .cache/portfolio-tools/python Pillow
  PYTHONPATH=.cache/portfolio-tools/python .venv/bin/python scripts/showcase_gif.py
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("docs/assets"))
    args = parser.parse_args()
    names = ["tour-dashboard.png", "tour-monitor.png", "tour-incident.png", "tour-recovery.png"]
    frames = []
    for name in names:
        with Image.open(args.directory / name) as frame:
            frame = frame.convert("RGB")
            frame.thumbnail((1008, 770), Image.Resampling.LANCZOS)
            frames.append(frame.quantize(colors=128))
    target = args.directory / "showcase.gif"
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=[2600, 2600, 2600, 3200],
        loop=0,
        optimize=True,
        disposal=2,
    )
    evidence = {
        "file": target.name,
        "frames": names,
        "description": "Actual browser captures; resized and quantized only.",
        "width": frames[0].width,
        "height": frames[0].height,
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    (args.directory / "animation-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Created {target.name}: {evidence['bytes']} bytes, four actual browser frames.")


if __name__ == "__main__":
    main()
