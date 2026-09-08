import json
from pathlib import Path
from typing import Optional

import torch
from torch.utils.data import Dataset

from models.char_cnn.preprocess import CharPreprocessor


class CharCNNDataset(Dataset):

    def __init__(
        self,
        samples: list[dict],
        preprocessor: CharPreprocessor,
        cache_encoding: bool = True,
    ):
        self.samples = samples
        self.preprocessor = preprocessor
        self.cache_encoding = cache_encoding
        self._cache: list[Optional[tuple[torch.Tensor, int]]] = [None] * len(samples)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        if self.cache_encoding and self._cache[idx] is not None:
            return self._cache[idx]

        sample = self.samples[idx]
        file_path = Path(sample["file_path"])

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            text = ""

        encoded = self.preprocessor.encode(text)
        label = sample["label"]
        result = (torch.tensor(encoded, dtype=torch.long), label)

        if self.cache_encoding:
            self._cache[idx] = result

        return result

    @classmethod
    def from_manifest(
        cls,
        manifest_path: Path,
        preprocessor: CharPreprocessor,
        split: str = "train",
        cache_encoding: bool = True,
    ) -> "CharCNNDataset":
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["splits"].get(split, []), preprocessor, cache_encoding)
