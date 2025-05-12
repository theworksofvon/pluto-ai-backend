from unsloth import FastLanguageModel
import torch
from datasets import load_dataset

max_seq_length = 2048
dtype = None  # Auto detection
load_in_4bit = False

MODEL_TO_TRAIN = "outputs_llama_3_2_3B/checkpoint-2319"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_TO_TRAIN,
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)

dataset = load_dataset(
    "json", data_files="crypto_tweets_conversational_diverse.jsonl", split="train"
)


def formatting_prompts_func(examples):
    texts = [
        tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        for example in examples["messages"]
    ]
    return {"text": texts}


dataset = dataset.map(formatting_prompts_func, batched=True)

from unsloth.chat_templates import get_chat_template

tokenizer = get_chat_template(
    tokenizer,
    chat_template="llama-3.1",
)

from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer),
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs=1,
        learning_rate=2e-4,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=1,
        optim="adamw_torch",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs_llama_3_2_3B_tweet_run",
        report_to="none",
    ),
)

from unsloth.chat_templates import train_on_responses_only

trainer = train_on_responses_only(
    trainer,
    instruction_part="<|start_header_id|>user<|end_header_id|>\n\n",
    response_part="<|start_header_id|>assistant<|end_header_id|>\n\n",
)

trainer_stats = trainer.train()
print(trainer_stats)
