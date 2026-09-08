#!/usr/bin/env python3
"""
fine_tune_graphcodebert.py — Fine-tuning LoRA de GraphCodeBERT en C/C++

Uso:
  # En tu PC con GPU:
  pip install torch transformers datasets peft bitsandbytes accelerate
  python fine_tune_graphcodebert.py --epochs 3 --save-to ./adaptador-lora

  # Subir a HuggingFace (opcional):
  python fine_tune_graphcodebert.py --push-to-hub tu-usuario/graphcodebert-c-ft

Requiere: torch, transformers, datasets, peft, bitsandbytes
"""

import argparse
import json
import math
import random
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    RobertaForMaskedLM,
    RobertaTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
import bitsandbytes as bnb

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning LoRA de GraphCodeBERT en C/C++")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-samples", type=int, default=15000,
                        help="Archivos C/C++ a descargar de The Stack")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--save-to", type=Path, default=Path("modelos/weights/graphcodebert-ft"))
    parser.add_argument("--push-to-hub", type=str, default=None,
                        help="Subir adaptador a HuggingFace (ej: tu-user/graphcodebert-c-ft)")
    args = parser.parse_args()

    print("=" * 60)
    print("Fine-tuning LoRA de GraphCodeBERT en C/C++")
    print("=" * 60)
    print(f"GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB)")
    print(f"Batch: {args.batch_size} | Epochs: {args.epochs} | Max samples: {args.max_samples}")
    print()

    # ─── 1. DATASET ───
    print("[1/4] Descargando The Stack Smol (C/C++ pre-filtrado)...")
    # the-stack-smol tiene splits por lenguaje: más rápido que filtrar The Stack completo
    c_dataset = load_dataset("bigcode/the-stack-smol", split="c", streaming=True, trust_remote_code=True)
    cpp_dataset = load_dataset("bigcode/the-stack-smol", split="cpp", streaming=True, trust_remote_code=True)

    from itertools import islice
    c_samples = list(islice(c_dataset, args.max_samples // 2))
    cpp_samples = list(islice(cpp_dataset, args.max_samples // 2))
    all_samples = c_samples + cpp_samples
    random.shuffle(all_samples)
    code_dataset = [{"text": s["content"]} for s in all_samples if s.get("content")]

    # Pequeña muestra para validación
    all_texts = list(code_dataset)
    random.shuffle(all_texts)
    n_val = max(1, len(all_texts) // 50)
    train_texts = [t["text"] for t in all_texts[n_val:]]
    val_texts = [t["text"] for t in all_texts[:n_val]]
    print(f"  Train: {len(train_texts)} | Val: {len(val_texts)}")

    # ─── 2. MODELO ───
    print("[2/4] Cargando GraphCodeBERT + QLoRA...")
    model_name = "microsoft/graphcodebert-base"
    tokenizer = RobertaTokenizer.from_pretrained(model_name)

    bnb_config = bnb.BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = RobertaForMaskedLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.FEATURE_EXTRACTION,
        target_modules=["query", "key", "value", "dense"],
    )
    model = get_peft_model(model, lora_config)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Params entrenables: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # ─── 3. TOKENIZACIÓN ───
    print("[3/4] Tokenizando...")

    class TextDataset(torch.utils.data.Dataset):
        def __init__(self, texts, tok, max_len):
            self.input_ids = [
                tok.encode(t, truncation=True, max_length=max_len)
                for t in texts
            ]
        def __len__(self):
            return len(self.input_ids)
        def __getitem__(self, i):
            return {"input_ids": torch.tensor(self.input_ids[i], dtype=torch.long)}

    train_ds = TextDataset(train_texts, tokenizer, args.max_length)
    val_ds = TextDataset(val_texts, tokenizer, args.max_length)
    print(f"  Train samples: {len(train_ds)}")

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=True, mlm_probability=0.15,
    )

    # ─── 4. ENTRENAMIENTO ───
    print("[4/4] Entrenando...")
    args.save_to.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(args.save_to),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=2,
        save_strategy="epoch",
        eval_strategy="epoch",
        logging_steps=20,
        learning_rate=args.lr,
        warmup_steps=200,
        report_to="none",
        fp16=True,
        dataloader_num_workers=0,
        remove_unused_columns=False,
        save_total_limit=1,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=train_ds,
        eval_dataset=val_ds,
    )
    trainer.train()

    # ─── GUARDAR ───
    final_path = args.save_to / "final"
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))
    print(f"\n✓ Adaptador LoRA guardado en: {final_path.resolve()}")
    print(f"  Tamaño: {sum(f.stat().st_size for f in final_path.rglob('*'))/1e6:.1f} MB")

    # Métricas
    eval_res = trainer.evaluate()
    perplexity = math.exp(eval_res["eval_loss"])
    print(f"  Perplejidad final: {perplexity:.2f}")
    with open(args.save_to / "metrics.json", "w") as f:
        json.dump({"perplexity": perplexity, **eval_res}, f, indent=2)

    # Push a HuggingFace
    if args.push_to_hub:
        from huggingface_hub import HfApi
        api = HfApi()
        api.upload_folder(folder_path=str(final_path), repo_id=args.push_to_hub)
        print(f"✓ Subido a HuggingFace: {args.push_to_hub}")

    print()
    print("=" * 60)
    print("¡Listo!")
    print()
    print("Para usar el adaptador en inference.py, cargá:")
    print()
    print("  from peft import PeftModel")
    print('  model = RobertaModel.from_pretrained("microsoft/graphcodebert-base")')
    print(f'  model = PeftModel.from_pretrained(model, "{final_path.resolve()}")')
    print()
    print("O desde HuggingFace:")
    if args.push_to_hub:
        print(f'  model = PeftModel.from_pretrained(model, "{args.push_to_hub}")')
    print("=" * 60)


if __name__ == "__main__":
    main()
