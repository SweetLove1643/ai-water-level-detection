#!/usr/bin/env python3
# python ./fine_tune_yolo\analyze_dataset.py --dataset ./resources\data\yolo_train\total
"""Basic checks and statistics for a YOLO segmentation dataset."""
from pathlib import Path
import argparse, json, collections, csv

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Dataset root created by build_dataset.py")
    args = ap.parse_args()
    root = Path(args.dataset)
    image_dir = root / "images" / "all"
    label_dir = root / "labels" / "all"
    classes_path = root / "classes.txt"
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise SystemExit("Expected images/all and labels/all under dataset root.")
    classes = [x.strip() for x in classes_path.read_text(encoding="utf-8").splitlines() if x.strip()] if classes_path.exists() else []
    image_map = {p.stem: p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS}
    label_map = {p.stem: p for p in label_dir.glob("*.txt")}
    per_class = collections.Counter()
    per_image_objects = []
    empty_labels = 0
    malformed = []
    for stem, img in sorted(image_map.items()):
        lp = label_map.get(stem)
        if lp is None:
            malformed.append({"image": img.name, "issue": "missing_label_txt"})
            continue
        lines = [line.strip() for line in lp.read_text(encoding="utf-8").splitlines() if line.strip()]
        count = 0
        for line_no, line in enumerate(lines, 1):
            vals = line.split()
            try:
                cls_id = int(vals[0])
                coords = [float(v) for v in vals[1:]]
                if cls_id < 0 or cls_id >= len(classes):
                    raise ValueError(f"class id {cls_id} outside classes.txt range")
                if len(coords) < 6 or len(coords) % 2:
                    raise ValueError("segmentation line needs >= 3 x/y pairs")
                if any(v < 0 or v > 1 for v in coords):
                    raise ValueError("normalized coordinate outside [0, 1]")
                per_class[classes[cls_id]] += 1
                count += 1
            except Exception as e:
                malformed.append({"image": img.name, "issue": f"line {line_no}: {e}"})
        if not lines:
            empty_labels += 1
        per_image_objects.append(count)

    extra_labels = sorted(set(label_map) - set(image_map))
    report = {
        "images": len(image_map), "label_txt_files": len(label_map),
        "classes": classes, "object_instances_by_class": dict(per_class),
        "images_with_empty_labels": empty_labels,
        "images_missing_label_txt": sum(1 for x in malformed if x["issue"] == "missing_label_txt"),
        "label_files_without_image": extra_labels,
        "malformed_entries": malformed,
        "objects_per_image": {
            "min": min(per_image_objects) if per_image_objects else 0,
            "max": max(per_image_objects) if per_image_objects else 0,
            "mean": round(sum(per_image_objects) / len(per_image_objects), 3) if per_image_objects else 0
        }
    }
    (root / "analysis_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (root / "class_distribution.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["class", "instances"])
        for name in classes: w.writerow([name, per_class[name]])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nSaved: {root / 'analysis_report.json'} and {root / 'class_distribution.csv'}")

if __name__ == "__main__":
    main()
