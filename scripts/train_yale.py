# train_yale.py
"""
Training script for the Yale Face Database.

The script loads the images from `data/yale`, creates a train/validation split,
applies basic preprocessing, and fine‑tunes a ResNet‑18 model (pre‑trained on ImageNet).
It saves the trained model weights to `models/yale_face.pth`.

Usage:
    python scripts\train_yale.py
"""

import os
import random
from pathlib import Path
from typing import List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from torchvision import models, transforms
from PIL import Image

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
DATA_ROOT = Path("data/yale")               # directory with the images
OUTPUT_DIR = Path("models")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = OUTPUT_DIR / "yale_face.pth"

BATCH_SIZE = 64
NUM_EPOCHS = 20
LR = 1e-3
VAL_SPLIT = 0.2
RANDOM_SEED = 42

# ------------------------------------------------------------
# Helper utilities
# ------------------------------------------------------------
def get_image_paths(root: Path) -> List[Path]:
    """Return a list of all image files under ``root``.
    The Yale dataset uses GIF files; Pillow can read them directly.
    """
    return sorted([p for p in root.rglob("*.gif")])

def label_from_path(path: Path) -> int:
    """Extract the subject identifier from a file name.
    Example: ``subject03.happy`` -> label 2 (zero‑based index).
    """
    # Filename format: subjectXX.<expression>
    name = path.stem  # remove .gif extension
    subject = name.split(".")[0]  # 'subject03'
    # Convert to integer index (subject01 -> 0)
    return int(subject.replace("subject", "")) - 1

class YaleDataset(Dataset):
    def __init__(self, image_paths: List[Path], transform=None):
        self.image_paths = image_paths
        self.transform = transform
        self.labels = [label_from_path(p) for p in image_paths]

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        img_path = self.image_paths[idx]
        # Pillow reads GIF as RGB (3 channels). Convert to RGB.
        image = Image.open(img_path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        label = self.labels[idx]
        return image, label

# ------------------------------------------------------------
# Main training routine
# ------------------------------------------------------------
def main():
    torch.manual_seed(RANDOM_SEED)
    random.seed(RANDOM_SEED)

    # 1️⃣ Load image paths and create dataset
    all_paths = get_image_paths(DATA_ROOT)
    if not all_paths:
        raise RuntimeError(f"No images found under {DATA_ROOT}. Did you run the download script?")

    transform = transforms.Compose([
        transforms.Resize((112, 92)),   # original Yale images are 112x92
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])

    dataset = YaleDataset(all_paths, transform=transform)
    val_len = int(len(dataset) * VAL_SPLIT)
    train_len = len(dataset) - val_len
    train_set, val_set = random_split(dataset, [train_len, val_len])

    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    # 2️⃣ Model – fine‑tune a ResNet‑18 (replace final FC layer)
    model = models.resnet18(pretrained=True)
    num_classes = 15  # 15 subjects in Yale
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    model = model.to("cpu")  # change to "cuda" if GPU is available

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LR)

    # 3️⃣ Training loop
    for epoch in range(1, NUM_EPOCHS + 1):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)
        epoch_loss = running_loss / train_len

        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                outputs = model(images)
                _, preds = torch.max(outputs, 1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)
        val_acc = correct / total * 100
        print(f"Epoch [{epoch}/{NUM_EPOCHS}] – Loss: {epoch_loss:.4f} – Val Acc: {val_acc:.2f}%")

    # 4️⃣ Save the trained model
    torch.save(model.state_dict(), MODEL_PATH)
    print(f"Training complete. Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    main()
