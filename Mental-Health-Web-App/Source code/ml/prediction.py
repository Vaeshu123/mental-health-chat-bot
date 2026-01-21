import torch
import pandas as pd
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

"""# Loading model"""

MODEL_PATH = "ml/distilbert-mental-health-stratified"

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
    confidence = int(round(max_value, 2) * 100)

    return max_label, confidence

r=predict_percentage("Too much work pressure")
print(r)