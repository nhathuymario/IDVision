# download_yale_dataset.py
"""Download Yale Face Database via kagglehub.

This script fetches the latest version of the dataset from Kaggle, extracts it
(if it is a zip) and copies the content into the project's `data/yale` folder.

Prerequisites:
- `pip install kagglehub`
- A valid Kaggle API token placed at `%USERPROFILE%\.kaggle\kaggle.json` (Windows)
  or `~/.kaggle/kaggle.json` (Linux/macOS).
"""
import os
import shutil
from pathlib import Path
import kagglehub

def main() -> None:
    # 1️⃣ Download dataset (KaggleHub handles caching & extraction)
    try:
        dataset_path = kagglehub.dataset_download("olgabelitskaya/yale-face-database")
    except Exception as e:
        raise RuntimeError(f"Failed to download Kaggle dataset: {e}")

    print(f"Dataset downloaded to: {dataset_path}")

    # 2️⃣ Prepare target directory inside the project
    target_dir = Path("data", "yale")
    target_dir.mkdir(parents=True, exist_ok=True)

    # 3️⃣ Copy all files/folders from the Kaggle cache to our data folder
    src_path = Path(dataset_path)
    for item in src_path.iterdir():
        dest = target_dir / item.name
        if dest.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    print(f"Yale Face Database is ready at {target_dir}")

if __name__ == "__main__":
    main()
