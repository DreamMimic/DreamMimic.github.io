#!/usr/bin/env python3
"""Compose a DreamMimic project-page overview video.

Logical order:
  1) Title card
  2) Chapter cards + demos:
     Perception -> SMPL-X -> Unitree G1 -> Long-horizon -> Sim2Sim

Example:
  python scripts/make_overview_video.py
  python scripts/make_overview_video.py --speed 1.0 --cell-duration 8
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from moviepy import (
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ROOT = ROOT / "static" / "videos"
OUT_DEFAULT = VIDEO_ROOT / "overview.mp4"

W, H = 1600, 900
FPS = 24
GAP = 6
BANNER_H = 64
PAD = 14
CHAPTER_DUR = 1.75
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Brand palette (paper / IROS page)
BG = (14, 18, 28)
NAVY = (0, 45, 114)
ACCENT = (240, 193, 75)  # gold
LINE = (70, 110, 160)

# Prefer this object order for grids (matches OMOMO paper objects).
OBJECT_ORDER = [
    "woodchair",
    "largetable",
    "largebox",
    "plasticbox",
    "smallbox",
    "suitecase",
]

LABEL = {
    "woodchair": "Chair",
    "largetable": "Table",
    "largebox": "Large box",
    "plasticbox": "Plastic box",
    "smallbox": "Small box",
    "suitecase": "Suitcase",
    "suitcase": "Suitcase",
}


def discover_seqs(platform_dir: Path) -> dict[str, list[Path]]:
    """Return {object_key: [seq paths sorted by index]}."""
    by_obj: dict[str, list[tuple[int, Path]]] = {}
    if not platform_dir.exists():
        return {}
    for obj_dir in sorted(platform_dir.iterdir()):
        if not obj_dir.is_dir():
            continue
        key = obj_dir.name
        for p in obj_dir.glob("seq*.mp4"):
            m = re.search(r"seq(\d+)", p.stem)
            idx = int(m.group(1)) if m else 0
            by_obj.setdefault(key, []).append((idx, p))
    return {
        k: [p for _, p in sorted(v, key=lambda t: t[0])]
        for k, v in by_obj.items()
    }


def pick_grid(by_obj: dict[str, list[Path]], n: int) -> list[tuple[str, Path]]:
    """Fill up to n slots with unique clips (never reuse a source file)."""
    keys = [k for k in OBJECT_ORDER if k in by_obj and by_obj[k]]
    keys += [k for k in sorted(by_obj) if k not in keys and by_obj[k]]
    if not keys:
        return []

    ptr = {k: 0 for k in keys}
    picked: list[tuple[str, Path]] = []
    while len(picked) < n:
        progressed = False
        for k in keys:
            if len(picked) >= n:
                break
            paths = by_obj[k]
            i = ptr[k]
            if i >= len(paths):
                continue
            picked.append((k, paths[i]))
            ptr[k] = i + 1
            progressed = True
        if not progressed:
            break
    return picked[:n]


def _no_loop_pad(clip, duration: float):
    """Play once; if short, hold the last frame (never loop)."""
    if clip.duration >= duration - 1e-3:
        return clip.subclipped(0, duration)
    t_end = max(0.0, clip.duration - 1.0 / FPS)
    freeze = clip.to_ImageClip(t=t_end).with_duration(duration - clip.duration)
    return concatenate_videoclips([clip, freeze])


def fit_clip(path: Path, cell_w: int, cell_h: int, duration: float, speed: float):
    clip = VideoFileClip(str(path)).without_audio()
    if abs(speed - 1.0) > 1e-3:
        clip = clip.with_effects([vfx.MultiplySpeed(speed)])
    clip = _no_loop_pad(clip, duration)
    tw, th = clip.size
    scale = max(cell_w / tw, cell_h / th)
    clip = clip.resized(scale)
    tw, th = clip.size
    x1 = max(0, int((tw - cell_w) / 2))
    y1 = max(0, int((th - cell_h) / 2))
    return clip.cropped(x1=x1, y1=y1, width=cell_w, height=cell_h)


def fit_letterbox(path: Path, box_w: int, box_h: int, duration: float, speed: float):
    """Fit video inside box without cropping (letterbox)."""
    clip = VideoFileClip(str(path)).without_audio()
    if abs(speed - 1.0) > 1e-3:
        clip = clip.with_effects([vfx.MultiplySpeed(speed)])
    clip = _no_loop_pad(clip, duration)
    tw, th = clip.size
    scale = min(box_w / tw, box_h / th)
    clip = clip.resized(scale)
    return clip


def chapter_card(
    index: int,
    title: str,
    subtitle: str,
    duration: float = CHAPTER_DUR,
):
    """Premium interstitial between demo blocks."""
    bg = ColorClip(size=(W, H), color=BG).with_duration(duration)
    # Left brand rail
    rail = ColorClip(size=(8, H), color=NAVY).with_duration(duration).with_position((0, 0))
    # Soft mid panel
    panel = (
        ColorClip(size=(W, int(H * 0.42)), color=(22, 30, 46))
        .with_opacity(0.55)
        .with_duration(duration)
        .with_position((0, int(H * 0.29)))
    )
    # Accent rule under title area
    rule = (
        ColorClip(size=(280, 3), color=ACCENT)
        .with_duration(duration)
        .with_position(((W - 280) // 2, int(H * 0.52)))
    )
    layers = [bg, rail, panel, rule]

    try:
        eyebrow = (
            TextClip(
                text=f"{index:02d}  /  CHAPTER",
                font=FONT,
                font_size=20,
                color="#8FB4D9",
                method="caption",
                size=(W - 200, 36),
                text_align="center",
            )
            .with_duration(duration)
            .with_position(("center", H * 0.34))
        )
        main = (
            TextClip(
                text=title,
                font=FONT_BOLD,
                font_size=58,
                color="white",
                method="caption",
                size=(W - 220, 90),
                text_align="center",
            )
            .with_duration(duration)
            .with_position(("center", H * 0.40))
        )
        sub = (
            TextClip(
                text=subtitle,
                font=FONT,
                font_size=24,
                color="#B8D4F0",
                method="caption",
                size=(W - 280, 70),
                text_align="center",
            )
            .with_duration(duration)
            .with_position(("center", H * 0.56))
        )
        layers.extend([eyebrow, main, sub])
    except Exception as e:
        print(f"[warn] chapter_card TextClip failed: {e}")

    card = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    return card.with_effects([vfx.FadeIn(0.28), vfx.FadeOut(0.28)])


def title_card(duration: float = 3.2):
    bg = ColorClip(size=(W, H), color=BG).with_duration(duration)
    rail = ColorClip(size=(8, H), color=NAVY).with_duration(duration).with_position((0, 0))
    rule = (
        ColorClip(size=(220, 3), color=ACCENT)
        .with_duration(duration)
        .with_position(((W - 220) // 2, int(H * 0.57)))
    )
    layers = [bg, rail, rule]
    try:
        t1 = (
            TextClip(
                text="DreamMimic",
                font=FONT_BOLD,
                font_size=76,
                color="white",
                method="caption",
                size=(W - 80, 100),
                text_align="center",
            )
            .with_duration(duration)
            .with_position(("center", H * 0.28))
        )
        t2 = (
            TextClip(
                text="Learning Visuomotor Whole-Body Loco-Manipulation via World Model",
                font=FONT,
                font_size=28,
                color="#B8D4F0",
                method="caption",
                size=(W - 140, 90),
                text_align="center",
            )
            .with_duration(duration)
            .with_position(("center", H * 0.44))
        )
        t3 = (
            TextClip(
                text="Accepted to IROS 2026",
                font=FONT,
                font_size=30,
                color="#F0C14B",
                method="caption",
                size=(W - 140, 50),
                text_align="center",
            )
            .with_duration(duration)
            .with_position(("center", H * 0.60))
        )
        layers.extend([t1, t2, t3])
    except Exception as e:
        print(f"[warn] title TextClip failed: {e}")
    card = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    return card.with_effects([vfx.FadeIn(0.35), vfx.FadeOut(0.30)])


def solo_scene(path: Path, caption: str, duration: float, speed: float):
    """Full-frame solo clip with a top caption banner."""
    bg = ColorClip(size=(W, H), color=BG).with_duration(duration)
    banner = ColorClip(size=(W, BANNER_H), color=NAVY).with_duration(duration)
    layers = [bg, banner.with_position((0, 0))]

    try:
        title = (
            TextClip(
                text=caption,
                font=FONT,
                font_size=32,
                color="white",
                method="caption",
                size=(W - 40, BANNER_H - 10),
                text_align="center",
            )
            .with_duration(duration)
            .with_position((20, 10))
        )
        layers.append(title)
    except Exception as e:
        print(f"[warn] solo caption failed: {e}")

    box_w = W - 2 * PAD
    box_h = H - BANNER_H - 2 * PAD
    clip = fit_letterbox(path, box_w, box_h, duration, speed)
    cw, ch = clip.size
    x = (W - cw) // 2
    y = BANNER_H + PAD + (box_h - ch) // 2
    layers.append(clip.with_position((x, y)))
    scene = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    return scene.with_effects([vfx.FadeIn(0.22)])


def grid_scene(
    picks: list[tuple[str, Path]],
    rows: int,
    cols: int,
    caption: str,
    duration: float,
    speed: float,
    platform_tag: str = "",
):
    assert len(picks) >= rows * cols, f"need {rows * cols} clips, got {len(picks)}"
    picks = picks[: rows * cols]

    usable_h = H - BANNER_H - PAD
    usable_w = W - 2 * PAD
    cell_w = (usable_w - GAP * (cols - 1)) // cols
    cell_h = (usable_h - GAP * (rows - 1)) // rows
    label_h = 22

    bg = ColorClip(size=(W, H), color=BG).with_duration(duration)
    banner = ColorClip(size=(W, BANNER_H), color=NAVY).with_duration(duration)
    layers = [bg, banner.with_position((0, 0))]

    try:
        title = (
            TextClip(
                text=caption,
                font=FONT,
                font_size=32,
                color="white",
                method="caption",
                size=(W - 40, BANNER_H - 10),
                text_align="center",
            )
            .with_duration(duration)
            .with_position((20, 10))
        )
        layers.append(title)
    except Exception as e:
        print(f"[warn] caption TextClip failed: {e}")

    for i, (obj_key, path) in enumerate(picks):
        r, c = divmod(i, cols)
        x = PAD + c * (cell_w + GAP)
        y = BANNER_H + PAD // 2 + r * (cell_h + GAP)
        cell = fit_clip(path, cell_w, cell_h - label_h, duration, speed)
        layers.append(cell.with_position((x, y)))

        label_text = LABEL.get(obj_key, obj_key)
        if platform_tag:
            label_text = f"{platform_tag} - {label_text}"
        m = re.search(r"seq(\d+)", path.stem)
        if m:
            label_text = f"{label_text} - seq{m.group(1)}"

        layers.append(
            ColorClip(size=(cell_w, label_h), color=(12, 16, 24))
            .with_opacity(0.75)
            .with_duration(duration)
            .with_position((x, y + cell_h - label_h))
        )
        try:
            lbl = (
                TextClip(
                    text=label_text,
                    font=FONT,
                    font_size=14,
                    color="white",
                    method="caption",
                    size=(cell_w - 4, label_h - 2),
                    text_align="center",
                )
                .with_duration(duration)
                .with_position((x + 2, y + cell_h - label_h + 1))
            )
            layers.append(lbl)
        except Exception:
            pass

    scene = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    return scene.with_effects([vfx.FadeIn(0.22)])


def build(args):
    smplx = discover_seqs(VIDEO_ROOT / "new" / "student_smplx_by_object")
    g1 = discover_seqs(VIDEO_ROOT / "new" / "student_g1_by_object")
    n_smplx = sum(len(v) for v in smplx.values())
    n_g1 = sum(len(v) for v in g1.values())
    print(f"Found {n_smplx} SMPL-X seqs, {n_g1} G1 seqs")

    scenes = []
    chapters = []  # (label, start_sec) for page timestamp links

    def add_scene(label: str, clip):
        chapters.append((label, sum(s.duration for s in scenes)))
        scenes.append(clip)

    def add_chapter(index: int, label: str, title: str, subtitle: str):
        add_scene(
            label,
            chapter_card(index=index, title=title, subtitle=subtitle, duration=CHAPTER_DUR),
        )

    add_scene("Title", title_card(3.2))

    grid_duration = args.cell_duration
    solo_duration = max(6.0, args.cell_duration)

    # Narrative: perception -> SMPL-X -> G1 -> robustness (long-horizon + sim2sim)
    add_chapter(
        1,
        "Perception",
        "Perception Inputs",
        "Depth and segmentation for world-model features",
    )
    add_scene(
        "Perception demo",
        solo_scene(
            VIDEO_ROOT / "box.mp4",
            "Perception Inputs: Depth + Segmentation",
            solo_duration,
            args.speed,
        ),
    )

    smplx_picks = pick_grid(smplx, 16)
    if len(smplx_picks) < 16:
        print(f"[warn] only {len(smplx_picks)} unique SMPL-X clips; need 16")
    add_chapter(
        2,
        "SMPL-X",
        "SMPL-X on OMOMO",
        "Vision-based whole-body loco-manipulation",
    )
    add_scene(
        "SMPL-X demo",
        grid_scene(
            smplx_picks,
            rows=4,
            cols=4,
            caption="SMPL-X on OMOMO",
            duration=grid_duration,
            speed=args.speed,
        ),
    )

    g1_picks = pick_grid(g1, 16)
    if len(g1_picks) < 16:
        print(f"[warn] only {len(g1_picks)} unique G1 clips; need 16")
    add_chapter(
        3,
        "Unitree G1",
        "Unitree G1",
        "Cross-embodiment transfer on a 42-DoF humanoid",
    )
    add_scene(
        "G1 demo",
        grid_scene(
            g1_picks,
            rows=4,
            cols=4,
            caption="Unitree G1 on OMOMO",
            duration=grid_duration,
            speed=args.speed,
            platform_tag="G1",
        ),
    )

    add_chapter(
        4,
        "Long-horizon",
        "Long-horizon Tests",
        "Sustained contact-rich interaction on BEHAVE",
    )
    add_scene(
        "Long-horizon demo",
        solo_scene(
            VIDEO_ROOT / "container.mp4",
            "Robustness: Long-horizon (BEHAVE)",
            solo_duration,
            args.speed,
        ),
    )

    add_chapter(
        5,
        "Sim2Sim",
        "Sim2Sim Transfer",
        "Isaac Gym to Isaac Lab under matched sequences",
    )
    add_scene(
        "Sim2Sim demo",
        solo_scene(
            VIDEO_ROOT / "isaaclab.mp4",
            "Robustness: Sim2Sim (Isaac Gym -> Isaac Lab)",
            solo_duration,
            args.speed,
        ),
    )

    print("Chapters:")
    for label, t0 in chapters:
        m, s = divmod(int(t0), 60)
        print(f"  [{m}:{s:02d}] {label}  ({t0:.1f}s)")

    final = concatenate_videoclips(scenes, method="compose")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = args.output.with_suffix(".tmp.mp4")
    print(f"Writing {args.output}  (~{final.duration:.1f}s @ {FPS}fps)")
    final.write_videofile(
        str(tmp_out),
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=8,
        bitrate="6000k",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    final.close()
    for s in scenes:
        s.close()
    tmp_out.replace(args.output)
    print(f"Done. Wrote {args.output}")
    print("HTML chapter seconds:", ",".join(f"{t:.1f}" for _, t in chapters))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Playback speed for source clips (1.0 = original).")
    # ~one full playback at 1x (raw clips are typically ~8-10s). Longer pads with a freeze, never a loop.
    parser.add_argument("--cell-duration", type=float, default=8.0)
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
