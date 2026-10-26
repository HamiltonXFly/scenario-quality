#!/usr/bin/env python
"""Record the README animation: three scenarios in esmini's top view, stacked.

Needs a display or Xvfb:  xvfb-run -a -s "-screen 0 1280x720x24" python scripts/record_gif.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps

DT, FPS, HOLD = 0.05, 10, 15
BOX = (470, 274, 1280, 394)       # ~12 m behind to ~46 m ahead of the ego (after mirroring)
STRIPS = [
    ("cutin_v100_dv-20_g20_t2", 1.0, "Useful test: the ego would have to brake at 1.2 m/s²"),
    ("cutin_v100_dv-40_g10_t2", 0.1, "Unavoidable: contact before the ego can react"),
    ("cutin_v100_dv-40_g35_t1", 1.0, "Implausible: 1 s lane change, 16 m/s² sideways"),
]


def capture(name: str, out: Path, scen: Path, esmini: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob("screen_shot_*.tga")):
        return
    subprocess.run([esmini, "--window", "0", "0", "1280", "720", "--osc", str((scen / f"{name}.xosc").resolve()),
                    "--fixed_timestep", str(DT), "--capture_screen", "--camera_mode", "top", "--disable_log"],
                   cwd=out, check=True, capture_output=True)


def main() -> None:
    root = Path("outputs")
    esmini = str(Path(os.environ.get("ESMINI_BIN", "esmini/bin/esmini")).resolve())
    res = pd.read_csv(root / "grid_results.csv").set_index("name")
    font = ImageFont.truetype("DejaVuSans.ttf", 17)
    small = ImageFont.truetype("DejaVuSans.ttf", 14)
    for name, _, _ in STRIPS:
        capture(name, root / "frames" / name, root / "grid" / "scenarios", esmini)

    def frame(name: str, t: float) -> Image.Image:
        i = max(0, round(t / DT))
        files = sorted((root / "frames" / name).glob("screen_shot_*.tga"))
        return ImageOps.mirror(Image.open(files[min(i, len(files) - 1)]).convert("RGB")).crop(BOX)

    W, H, LH = BOX[2] - BOX[0], BOX[3] - BOX[1], 30
    rel = [k / FPS for k in range(-30, 11)]          # 3 s before to 1 s after the cut-in
    frames = []
    for r in rel + [rel[-1]] * HOLD:
        canvas = Image.new("RGB", (W, (H + LH) * len(STRIPS) + 26), "white")
        d = ImageDraw.Draw(canvas)
        for j, (name, after, label) in enumerate(STRIPS):
            te = res.loc[name, "t_entry"]
            canvas.paste(frame(name, te + min(r, after)), (0, j * (H + LH) + LH))
            d.text((8, j * (H + LH) + 6), label, fill="#0b0b0b", font=font)
        d.text((8, canvas.height - 21), "grey = ego (constant speed), red = merging car, driving direction →",
               fill="#52514e", font=small)
        frames.append(canvas.resize((W * 4 // 5, canvas.height * 4 // 5), Image.LANCZOS))
    frames[0].save("docs/cutin_examples.gif", save_all=True, append_images=frames[1:],
                   duration=1000 // FPS, loop=0, optimize=True)


if __name__ == "__main__":
    main()
