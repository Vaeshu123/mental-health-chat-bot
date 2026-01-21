import torch
import pandas as pd
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

# Loading model

MODEL_PATH = "distilbert-mental-health-stratified"

tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_PATH)
model = DistilBertForSequenceClassification.from_pretrained(MODEL_PATH)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

LABEL_NAMES = [
    "suicidal_ideation",
    "depressive_language",
    "anxiety_related",
    "stress_related"
]

"""# Predicting"""

def predict(text):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits

    probs = torch.sigmoid(logits)[0]
    return {
        LABEL_NAMES[i]: float(probs[i])
        for i in range(len(LABEL_NAMES))
    }

def predict_percentage(text):
    output = predict(text)  # your model function

    # find label with max probability
    max_label = max(output, key=output.get)
    max_value = output[max_label]
    print("Predicted Label:", max_label, "->", int(round(max_value, 2)*100))

test_cases = [
    "I don’t want to live anymore",
    "I want to kill myself",
    "I feel empty every day",
    "work stress too much",
    "so tired from work",
    "deadlines again man",
    "Deadlines make me panic.",
    "Too much pressure makes me anxious.",
    "I feel overwhelmed and nervous.",
    "Work stress is making me panic.",
    "There is too much responsibility on me.",
    "I have too much work and no time to rest.",
    "My workload is getting heavier every week.",
    "I am anxious all the time",
    "I wake up empty every day and go to bed the same way.",
    "Nothing excites me anymore.",
    "I feel hollow inside."
]
print(f"{'Text':50} | {'Label':20} | Confidence")
print("-"*90)

for text in test_cases:
    output = predict(text)

    max_label = max(output, key=output.get)
    max_value = output[max_label]

    print(f"{text[:48]:50} | {max_label:20} | {round(max_value*100,2)}%")


