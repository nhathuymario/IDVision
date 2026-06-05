import os
import random
import shutil
from pathlib import Path
import argparse

def sample_images(src_dir: Path, dst_dir: Path, max_per_id: int = 5, val_ratio: float = 0.2):
    """Sample up to `max_per_id` images per person from src_dir (LFW or MAFA).
    Creates train/val splits under dst_dir.
    """
    train_dir = dst_dir / "train"
    val_dir = dst_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    # LFW structure: src_dir/lfw/*/*
    for person_dir in src_dir.iterdir():
        if not person_dir.is_dir():
            continue
        images = list(person_dir.glob("*.jpg"))
        if not images:
            continue
        random.shuffle(images)
        selected = images[:max_per_id]
        split = int(len(selected) * (1 - val_ratio))
        for img_path in selected[:split]:
            dst = train_dir / person_dir.name
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, dst / img_path.name)
        for img_path in selected[split:]:
            dst = val_dir / person_dir.name
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img_path, dst / img_path.name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a small balanced dataset from LFW and MAFA.")
    parser.add_argument("--src-lfw", type=str, required=True, help="Path to extracted LFW directory (e.g., data/lfw")")
    parser.add_argument("--src-mafa", type=str, required=True, help="Path to MAFA directory (e.g., data/mafa)")
    parser.add_argument("--dst", type=str, default="data/small", help="Destination directory for train/val split")
    parser.add_argument("--max-per-id", type=int, default=5, help="Maximum images per identity")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Fraction of images for validation")
    args = parser.parse_args()

    dst_path = Path(args.dst)
    # Process LFW
    print("Sampling from LFW...")
    sample_images(Path(args.src_lfw), dst_path, args.max_per_id, args.val_ratio)
    # Process MAFA – MAFA has a different structure (annotations + images). We'll just copy all jpgs.
    print("Sampling from MAFA (masked faces)...")
    mafa_images = list(Path(args.src_mafa).rglob("*.jpg"))
    random.shuffle(mafa_images)
    selected = mafa_images[:args.max_per_id * 100]  # limit total count
    split = int(len(selected) * (1 - args.val_ratio))
    for img_path in selected[:split]:
        dst = dst_path / "train" / "masked"
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img_path, dst / img_path.name)
    for img_path in selected[split:]:
        dst = dst_path / "val" / "masked"
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img_path, dst / img_path.name)
    print(f"Dataset created at {dst_path.resolve()}")
