"""Fine-tune facebook/nllb-200-distilled-600M on SeyhaLite/Translate-English-Khmer-All
for local, offline English -> Khmer subtitle translation.

Usage:
    python translator/scripts/finetune_nllb_km.py
    python translator/scripts/finetune_nllb_km.py --epochs 5 --batch-size 8
    python translator/scripts/finetune_nllb_km.py --sample 2000   # quick smoke test
    python translator/scripts/finetune_nllb_km.py --cpu           # force CPU

Output is written to translator/models/nllb-en-km-finetuned (default), which is
exactly where app/ai/local_mt.py:LocalNLLBProvider looks for a fine-tuned model.
"""
import argparse
import os

BASE_MODEL = "facebook/nllb-200-distilled-600M"
DATASET_ID = "SeyhaLite/Translate-English-Khmer-All"
SRC_LANG = "eng_Latn"
TGT_LANG = "khm_Khmr"

DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "nllb-en-km-finetuned"
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Where to save the fine-tuned model.")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch-size", type=int, default=16, help="Per-device train batch size.")
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--sample", type=int, default=0, help="If >0, train on only this many rows (smoke test).")
    p.add_argument("--val-size", type=int, default=2000, help="Rows held out for eval.")
    p.add_argument("--max-length", type=int, default=128)
    p.add_argument("--cpu", action="store_true", help="Force CPU even if a CUDA GPU is available.")
    p.add_argument("--resume-from-checkpoint", default=None)
    return p.parse_args()


def main():
    args = parse_args()

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )

    use_cuda = torch.cuda.is_available() and not args.cpu
    device = "cuda" if use_cuda else "cpu"
    print(f"[finetune_nllb_km] device={device}")

    print(f"[finetune_nllb_km] loading dataset {DATASET_ID} ...")
    ds = load_dataset(DATASET_ID, split="train")
    if args.sample > 0:
        ds = ds.select(range(min(args.sample, len(ds))))

    ds = ds.train_test_split(test_size=min(args.val_size, max(1, len(ds) // 20)), seed=42)
    train_ds, eval_ds = ds["train"], ds["test"]
    print(f"[finetune_nllb_km] train={len(train_ds)} eval={len(eval_ds)}")

    print(f"[finetune_nllb_km] loading base model {BASE_MODEL} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, src_lang=SRC_LANG, tgt_lang=TGT_LANG)
    model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL)
    model.to(device)

    def preprocess(batch):
        return tokenizer(
            batch["eng"],
            text_target=batch["kh"],
            max_length=args.max_length,
            truncation=True,
        )

    train_tok = train_ds.map(preprocess, batched=True, remove_columns=train_ds.column_names)
    eval_tok = eval_ds.map(preprocess, batched=True, remove_columns=eval_ds.column_names)

    collator = DataCollatorForSeq2Seq(tokenizer, model=model)

    training_args = Seq2SeqTrainingArguments(
        output_dir=os.path.join(args.output_dir, "_checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        predict_with_generate=True,
        fp16=use_cuda,
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to=[],
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=eval_tok,
        data_collator=collator,
        processing_class=tokenizer,
    )

    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)

    os.makedirs(args.output_dir, exist_ok=True)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"[finetune_nllb_km] saved fine-tuned model to {args.output_dir}")
    print("[finetune_nllb_km] LocalNLLBProvider will pick this up automatically — no config change needed.")


if __name__ == "__main__":
    main()
