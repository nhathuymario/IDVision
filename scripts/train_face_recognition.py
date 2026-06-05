import os
import argparse
from pathlib import Path
import torch
import insightface


def train(train_dir: Path, val_dir: Path, output_path: Path, epochs: int = 10, batch_size: int = 32, lr: float = 1e-4):
    """Train an ArcFace model on a tiny dataset.
    Uses InsightFace's training API with a ResNet‑50 backbone.
    """
    # Build a simple config dict as InsightFace expects
    cfg = {
        "backbone": "resnet50",
        "head": "arcface",
        "lr": lr,
        "batch_size": batch_size,
        "epochs": epochs,
        "train_dataset": str(train_dir),
        "val_dataset": str(val_dir),
        "log_interval": 10,
        "save_interval": 1,
        "save_path": str(output_path),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }
    # InsightFace provides a Trainer class (simplified here)
    from insightface.app import FaceModel
    from insightface.trainer import Trainer
    model = FaceModel(backbone=cfg["backbone"], head=cfg["head"]).to(cfg["device"])
    trainer = Trainer(model, cfg)
    trainer.run()
    print(f"Training completed. Checkpoint saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train face recognition model on tiny dataset.")
    parser.add_argument("--train-dir", type=str, required=True, help="Path to training images")
    parser.add_argument("--val-dir", type=str, required=True, help="Path to validation images")
    parser.add_argument("--output", type=str, default="models/face_arcface_finetuned.pth", help="Where to save checkpoint")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    train(Path(args.train_dir), Path(args.val_dir), Path(args.output), args.epochs, args.batch_size, args.lr)
