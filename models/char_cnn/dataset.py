import json
from pathlib import Path
from typing import Optional

import torch
from torch.utils.data import Dataset

from models.char_cnn.preprocess import CharPreprocessor


DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def rebase_path(file_path: str, data_root: Path = DEFAULT_DATA_ROOT) -> Path:
    """Map a manifest path recorded on another machine onto the local `data/` folder.

    Manifests store absolute paths (e.g. /home/user/.../data/raw/src/...). Anything after
    `data/{raw,output}` is kept; paths without that anchor are returned unchanged.
    """
    parts = Path(str(file_path).replace("\\", "/")).parts
    for i, part in enumerate(parts[:-1]):
        if part == "data" and parts[i + 1] in ("raw", "output"):
            return Path(data_root).joinpath(*parts[i + 1:])
    return Path(file_path)


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
        data_root: Path = DEFAULT_DATA_ROOT,
    ) -> "CharCNNDataset":
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        samples = []
        missing = []
        for s in data["splits"].get(split, []):
            path = Path(s["file_path"])
            if not path.exists():
                path = rebase_path(s["file_path"], data_root)
            if not path.exists():
                missing.append(s["file_path"])
            samples.append({**s, "file_path": str(path)})
        if missing:
            raise FileNotFoundError(
                f"{len(missing)}/{len(samples)} '{split}' files not found locally; first: {missing[0]}"
            )
        return cls(samples, preprocessor, cache_encoding)
