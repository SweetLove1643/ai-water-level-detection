#!/usr/bin/env python3
# python fine_tune_yolo\build_dataset.py --images ./resources/data/img_org --labels ./resources/data/labelme --out ./resources/data/yolo_train/total
"""Convert CVAT LabelMe 3.0 XML polygon annotations to YOLO segmentation format."""
from pathlib import Path
import argparse
import shutil
import xml.etree.ElementTree as ET
import json
import csv

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

def local_name(tag):
    return tag.rsplit("}", 1)[-1]

def child_text(node, name, default=""):
    for child in node:
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return default

def parse_xml(xml_path):
    root = ET.parse(xml_path).getroot()
    filename = child_text(root, "filename")
    width = height = None
    for node in root:
        if local_name(node.tag) == "imagesize":
            for sub in node:
                if local_name(sub.tag) == "ncols":
                    width = float((sub.text or "0").strip())
                elif local_name(sub.tag) == "nrows":
                    height = float((sub.text or "0").strip())
    if not width or not height:
        raise ValueError("missing/invalid imagesize ncols/nrows")

    objects = []
    for obj in root:
        if local_name(obj.tag) != "object":
            continue
        label = child_text(obj, "name")
        deleted = child_text(obj, "deleted", "0").lower()
        if deleted in {"1", "true", "yes"} or not label:
            continue
        polygon = None
        for child in obj:
            if local_name(child.tag) == "polygon":
                polygon = child
                break
        if polygon is None:
            continue
        points = []
        for pt in polygon:
            if local_name(pt.tag) != "pt":
                continue
            x = y = None
            for coord in pt:
                if local_name(coord.tag) == "x":
                    x = float((coord.text or "0").strip())
                elif local_name(coord.tag) == "y":
                    y = float((coord.text or "0").strip())
            if x is not None and y is not None:
                # Clamp coordinates to image bounds before normalization.
                x = min(max(x, 0.0), width)
                y = min(max(y, 0.0), height)
                points.append((x / width, y / height))
        # YOLO segmentation needs at least 3 distinct vertices.
        if len(points) >= 3:
            objects.append({"label": label, "points": points})
    return filename, int(width), int(height), objects

def read_classes(classes_file, labels):
    if classes_file:
        classes = [line.strip() for line in Path(classes_file).read_text(encoding="utf-8-sig").splitlines()
                   if line.strip() and not line.strip().startswith("#")]
        if not classes:
            raise ValueError("classes file is empty")
        missing = sorted(set(labels) - set(classes))
        if missing:
            raise ValueError(f"classes.txt is missing labels found in XML: {missing}")
        if len(classes) != len(set(classes)):
            raise ValueError("classes.txt contains duplicate class names")
        return classes
    return sorted(set(labels))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", required=True, help="Folder containing original images")
    ap.add_argument("--labels", required=True, help="Folder containing per-image XML annotation files")
    ap.add_argument("--out", required=True, help="Output dataset folder")
    ap.add_argument("--classes", default=None, help="Optional text file: one class name per line, in desired class-ID order")
    ap.add_argument("--copy", action="store_true", help="Copy images (default). Kept for compatibility; copying is always used.")
    args = ap.parse_args()

    image_dir, xml_dir, out_dir = Path(args.images), Path(args.labels), Path(args.out)
    if not image_dir.is_dir():
        raise SystemExit(f"Image folder not found: {image_dir}")
    if not xml_dir.is_dir():
        raise SystemExit(f"XML folder not found: {xml_dir}")

    images_by_stem = {}
    for p in image_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            # Prefer a unique stem; warn/report ambiguity rather than silently picking one.
            images_by_stem.setdefault(p.stem, []).append(p)

    xml_files = sorted(xml_dir.rglob("*.xml"))
    if not xml_files:
        raise SystemExit(f"No .xml files found under: {xml_dir}")

    parsed = []
    errors = []
    all_labels = set()
    for xp in xml_files:
        try:
            xml_filename, width, height, objects = parse_xml(xp)
            # Prefer XML's <filename>; if unavailable, use XML filename stem.
            wanted_name = Path(xml_filename).name if xml_filename else xp.stem
            candidates = images_by_stem.get(Path(wanted_name).stem, [])
            if len(candidates) > 1:
                # Exact filename match resolves common same-stem/different-extension cases.
                exact = [p for p in candidates if p.name.lower() == wanted_name.lower()]
                candidates = exact if len(exact) == 1 else candidates
            if len(candidates) != 1:
                errors.append({"xml": str(xp), "source_image": wanted_name, "output_image": "",
                               "width": "", "height": "", "objects": "", "classes": "",
                               "status": "image_not_found" if not candidates else "ambiguous_image_stem"})
                continue
            for obj in objects:
                all_labels.add(obj["label"])
            parsed.append((xp, candidates[0], width, height, objects))
        except Exception as e:
            errors.append({"xml": str(xp), "source_image": "", "output_image": "", "width": "",
                           "height": "", "objects": "", "classes": "", "status": f"xml_parse_error: {e}"})

    classes = read_classes(args.classes, all_labels)
    class_to_id = {name: i for i, name in enumerate(classes)}
    images_out = out_dir / "images" / "all"
    labels_out = out_dir / "labels" / "all"
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    # Remove stale generated files from earlier runs, so outputs reflect this run.
    for p in list(images_out.iterdir()) + list(labels_out.iterdir()):
        if p.is_file():
            p.unlink()

    used_names = set()
    report = []
    for xp, image_path, width, height, objects in parsed:
        # Preserve original image filename; add a short stable suffix if duplicate names occur.
        out_name = image_path.name
        if out_name.lower() in used_names:
            out_name = f"{image_path.stem}_{xp.stem}{image_path.suffix}"
        used_names.add(out_name.lower())
        shutil.copy2(image_path, images_out / out_name)

        txt_path = labels_out / f"{Path(out_name).stem}.txt"
        lines = []
        for obj in objects:
            coords = []
            for x, y in obj["points"]:
                coords.extend([f"{x:.6f}", f"{y:.6f}"])
            lines.append(str(class_to_id[obj["label"]]) + " " + " ".join(coords))
        txt_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        report.append({
            "xml": str(xp), "source_image": str(image_path), "output_image": out_name,
            "width": width, "height": height, "objects": len(objects),
            "classes": ";".join(sorted({o["label"] for o in objects})), "status": "ok"
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "classes.txt").write_text("\n".join(classes) + ("\n" if classes else ""), encoding="utf-8")
    with (out_dir / "build_report.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["xml", "source_image", "output_image", "width", "height", "objects", "classes", "status"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(report)
        w.writerows(errors)
    summary = {
        "xml_files_found": len(xml_files), "matched_samples": len(parsed),
        "converted_samples": len(report), "errors_or_unmatched": len(errors),
        "class_to_id": class_to_id,
        "images_without_valid_polygons": sum(1 for r in report if r["objects"] == 0),
        "notes": "Only images paired with a valid XML are included. Matched XMLs with no valid polygon are included as negative samples."
    }
    (out_dir / "build_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nDataset created at: {out_dir.resolve()}")
    print(f"Review report: {out_dir / 'build_report.csv'}")

if __name__ == "__main__":
    main()
