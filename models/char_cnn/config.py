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

    unknown_char: str = "�"
    pad_char: str = " "

    # --- Secuencia ---
    seq_length: int = 2048

    # --- Arquitectura (Zhang et al. 2015 adaptada) ---
    embedding_dim: int = 256
    num_conv_layers: int = 6
    conv_kernel_sizes: tuple = (7, 7, 3, 3, 3, 3)
    conv_filters: tuple = (256, 256, 256, 256, 256, 256)
    pool_sizes: tuple = (3, 3, 0, 0, 0, 3)
    fc_units: tuple = (1024, 1024)
    num_classes: int = 2
    dropout: float = 0.5

    # --- Entrenamiento ---
    batch_size: int = 128
    epochs: int = 50
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    lr_patience: int = 3
    lr_factor: float = 0.5
    early_stop_patience: int = 7
    val_split: float = 0.15
    test_split: float = 0.15

    # --- Paths ---
    raw_student_dir: Path = Path("data/raw/src")
    synthetic_dir: Path = Path("data/output")
    manifest_path: Path = Path("models/char_cnn/dataset_manifest.json")
    weights_dir: Path = Path("modelos/weights")
    logs_dir: Path = Path("models/char_cnn/logs")

    # --- Balanceo ---
    max_samples_per_subproblem: int = 200
    seed: int = 42
