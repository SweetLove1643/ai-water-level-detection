#!/usr/bin/env python3
# python ./fine_tune_yolo\split_dataset.py --dataset ./resources\data\yolo_train\total --val-ratio 0.2 --seed 42
"""Create deterministic train/val split from images/all and labels/all."""
from pathlib import Path
import argparse, random, shutil, json

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Dataset root created by build_dataset.py")
    ap.add_argument("--val-ratio", type=float, default=0.2, help="Validation fraction, e.g. 0.2")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--link", action="store_true", help="Create hardlinks instead of copying when supported")
    args = ap.parse_args()
    if not 0 < args.val_ratio < 1:
        raise SystemExit("--val-ratio must be between 0 and 1")
    root = Path(args.dataset)
    src_images, src_labels = root / "images" / "all", root / "labels" / "all"
    if not src_images.is_dir() or not src_labels.is_dir():
        raise SystemExit("Expected images/all and labels/all under dataset root.")
    pairs = []
    for image in src_images.iterdir():
        if image.is_file() and image.suffix.lower() in IMAGE_EXTS:
            label = src_labels / f"{image.stem}.txt"
            if label.exists():
                pairs.append((image, label))
    if len(pairs) < 2:
        raise SystemExit(f"Need at least 2 image/label pairs; found {len(pairs)}")
    random.Random(args.seed).shuffle(pairs)
    n_val = max(1, round(len(pairs) * args.val_ratio))
    n_val = min(n_val, len(pairs) - 1)
    splits = {"train": pairs[n_val:], "val": pairs[:n_val]}
    for split, items in splits.items():
        img_out, lbl_out = root / "images" / split, root / "labels" / split
        img_out.mkdir(parents=True, exist_ok=True); lbl_out.mkdir(parents=True, exist_ok=True)
        # Clear prior split output to avoid stale files.
        for folder in (img_out, lbl_out):
            for p in folder.iterdir():
                if p.is_file(): p.unlink()
        for image, label in items:
            for src, dst in ((image, img_out / image.name), (label, lbl_out / label.name)):
                if dst.exists(): dst.unlink()
                if args.link:
                    try: dst.hardlink_to(src)
                    except OSError: shutil.copy2(src, dst)
                else:
                    shutil.copy2(src, dst)

    classes = [x.strip() for x in (root / "classes.txt").read_text(encoding="utf-8").splitlines() if x.strip()]
    yaml_lines = [
        f"path: {root.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "names:"
    ]
    yaml_lines += [f"  {i}: {name!r}" for i, name in enumerate(classes)]
    (root / "data.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    summary = {"total_pairs": len(pairs), "train": len(splits["train"]), "val": len(splits["val"]),
               "val_ratio_requested": args.val_ratio, "seed": args.seed}
    (root / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"YOLO data config: {root / 'data.yaml'}")

if __name__ == "__main__":
    main()
