from unsloth import FastLanguageModel
from enum import Enum
import torch
from datasets import load_dataset


class UnslothFourBitModels(Enum):
    LLAMA_3_1_8B = "unsloth/Meta-Llama-3.1-8B-bnb-4bit"  # Llama-3.1 2x faster
    LLAMA_3_1_8B_INSTRUCT = "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit"
    LLAMA_3_1_70B = "unsloth/Meta-Llama-3.1-70B-bnb-4bit"
    LLAMA_3_1_405B = "unsloth/Meta-Llama-3.1-405B-bnb-4bit"  # 4bit for 405b!
    MISTRAL_SMALL_2409 = "unsloth/Mistral-Small-Instruct-2409"  # Mistral 22b 2x faster!
    MISTRAL_7B_V03 = "unsloth/mistral-7b-instruct-v0.3-bnb-4bit"
    PHI_3_5_MINI = "unsloth/Phi-3.5-mini-instruct"  # Phi-3.5 2x faster!
    PHI_3_MEDIUM_4K = "unsloth/Phi-3-medium-4k-instruct"
    GEMMA_2_9B = "unsloth/gemma-2-9b-bnb-4bit"
    GEMMA_2_27B = "unsloth/gemma-2-27b-bnb-4bit"  # Gemma 2x faster!

    # New Llama 3.2 Models
    LLAMA_3_2_1B = "unsloth/Llama-3.2-1B-bnb-4bit"  # NEW! Llama 3.2 models
    LLAMA_3_2_1B_INSTRUCT = "unsloth/Llama-3.2-1B-Instruct-bnb-4bit"
    LLAMA_3_2_3B = "unsloth/Llama-3.2-3B-bnb-4bit"
    LLAMA_3_2_3B_INSTRUCT = "unsloth/Llama-3.2-3B-Instruct-bnb-4bit"

    # New Llama 3.3 Models
    LLAMA_3_3_70B_INSTRUCT = (
        "unsloth/Llama-3.3-70B-Instruct-bnb-4bit"  # NEW! Llama 3.3 70B!
    )


max_seq_length = 2048  # Choose any! We auto support RoPE Scaling internally!
dtype = (
    None  # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
)
load_in_4bit = False  # Use 4bit quantization to reduce memory usage. Can be False.
MODEL_TO_TRAIN = (
    "outputs_llama_3_2_3B/checkpoint-2319"  # "unsloth/Llama-3.2-3B-Instruct"
)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="outputs_llama_3_2_3B/checkpoint-2319",
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,  # Choose any number > 0 ! Suggested 8, 16, 32, 64, 128
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
    lora_dropout=0,  # Supports any, but = 0 is optimized
    bias="none",  # Supports any, but = "none" is optimized
    use_gradient_checkpointing="unsloth",  # True or "unsloth" for very long context
    random_state=3407,
    use_rslora=False,  # We support rank stabilized LoRA
    loftq_config=None,  # And LoftQ
)

dataset = load_dataset("andrewkroening/538-NBA-Historical-Raptor", split="train")


def prepare_conversations(data):
    conversations = []
    for name, season, raptor, war in zip(
        data["player_name"], data["season"], data["raptor_total"], data["war_total"]
    ):
        conversations.append(
            [
                {"role": "user", "content": f"What were {name}'s stats in {season}?"},
                {
                    "role": "assistant",
                    "content": f"In {season}, {name} had a RAPTOR score of {raptor} and WAR total of {war}.",
                },
            ]
        )
    return {"conversations": conversations}


# def prepare_conversations(data):
#     conversations = []
#     for name, season, poss, mp, raptor_total, war_total, pred_off, pred_def, pred_total, pace in zip(
#         data['player_name'], data['season'], data['poss'], data['mp'],
#         data['raptor_total'], data['war_total'],
#         data['predator_offense'], data['predator_defense'], data['predator_total'],
#         data['pace_impact']
#     ):
#         conversations.append([
#             {"role": "user": f"What were {name}'s key stats in {season}?"},
#             {"role": "assistant": (
#                 f"In {season}, {name} played {mp} minutes with {poss} possessions. "
#                 f"They had a RAPTOR score of {raptor_total}, a WAR total of {war_total}, and a "
#                 f"Predator score of {pred_total} (Offense: {pred_off}, Defense: {pred_def}). "
#                 f"Their pace impact was {pace}."
#             )},
#              {"role": "user": (
#                 f"How does {name}'s performance in {season} compare to their previous seasons for betting predictions?"
#             )},
#             {"role": "assistant": (
#                 f"{name}'s performance in {season} showed a RAPTOR score of {raptor_total} and WAR total of {war_total}. "
#                 f"Compared to previous seasons, their offensive Predator score ({pred_off}) and defensive Predator score ({pred_def}) "
#                 f"suggest a {'strong improvement' if pred_total > 0 else 'decline'} in impact. "
#                 f"This may indicate they are {'a valuable asset' if war_total > 0 else 'underperforming'} for betting predictions."
#             )},
#               {"role": "user": (
#                 f"How can I use {name}'s stats from {season} to predict whether their team will win an upcoming game?"
#             )},
#             {"role": "assistant": (
#                 f"{name}'s stats from {season} highlight a RAPTOR score of {raptor_total} and WAR total of {war_total}. "
#                 f"Their Predator metrics (Offense: {pred_off}, Defense: {pred_def}) suggest their impact on both ends of the court. "
#                 f"Consider matchups where the opposing team's defense struggles against high-paced players (Pace Impact: {pace}). "
#                 f"Teams relying on {name} for scoring or defensive support may outperform slower-paced or injury-laden opponents."
#             )}
#         ])
#     return {"conversations": conversations}

dataset = dataset.map(prepare_conversations, batched=True, batch_size=100)


from unsloth.chat_templates import get_chat_template

# Apply the chat template
tokenizer = get_chat_template(
    tokenizer,
    chat_template="llama-3.1",
)


# Format the prompts
def formatting_prompts_func(examples):
    convos = examples["conversations"]
    texts = [
        tokenizer.apply_chat_template(
            convo, tokenize=False, add_generation_prompt=False
        )
        for convo in convos
    ]
    return {"text": texts}


dataset = dataset.map(formatting_prompts_func, batched=True)

print(dataset[0])


# Train the model
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
        num_train_epochs=1,  # Set this for 1 full training run.
        # max_steps = 200,
        learning_rate=2e-4,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=1,
        optim="adamw_torch",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs_llama_3_2_3B_run_2",
        report_to="none",  # Use this for WandB etc
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
