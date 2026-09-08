from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CharCNNConfig:

    # --- Alfabeto ---
    alphabet: str = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "{}()[]<>;.,:!?+-*/%=&|^~#_@$'\"`\\ "
        "\n\t\r"
        "áéíóúüñÁÉÍÓÚÜÑ"
        "čćđšžČĆĐŠŽ"
    )

    unknown_char: str = ""
    pad_char: str = " "

    # --- Secuencia ---
    seq_length: int = 4096

    # --- Preprocesamiento ---
    strip_comments: bool = True
    normalize_whitespace: bool = True

    # --- Arquitectura Multi-Scale 1D CNN ---
    embedding_dim: int = 128
    conv_kernel_sizes: tuple = (3, 5, 7, 9)
    conv_filters: tuple = (64, 64, 64, 64)
    fc_units: tuple = (1024,)  # Dimensión del embedding latente
    num_classes: int = 2
    dropout: float = 0.4

    # --- Entrenamiento ---
    batch_size: int = 64
    epochs: int = 30
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    lr_patience: int = 3
    lr_factor: float = 0.5
    early_stop_patience: int = 6
    val_split: float = 0.15
    test_split: float = 0.15

    # --- Paths ---
    raw_student_dir: Path = Path("data/raw/src")
    synthetic_dir: Path = Path("data/output")
    manifest_path: Path = Path("models/char_cnn/dataset_manifest.json")
    weights_dir: Path = Path("models/char_cnn/weights")
    best_model_path: Path = Path("models/char_cnn/best_model.pth")
    logs_dir: Path = Path("models/char_cnn/logs")

    # --- Balanceo ---
    max_samples_per_subproblem: int = 50
    seed: int = 42

    def __post_init__(self):
        self.weights_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
