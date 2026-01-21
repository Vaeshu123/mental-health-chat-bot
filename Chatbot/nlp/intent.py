from transformers import pipeline

classifier = pipeline("zero-shot-classification")

LABELS = ["self-harm intent", "emotional distress", "neutral"]

def detect_intent(text):
    result = classifier(text, LABELS)
    scores = dict(zip(result["labels"], result["scores"]))

    if scores["self-harm intent"] > 0.6:
        return "self-harm"

    if scores["emotional distress"] > 0.5:
        return "distress"

    return "neutral"


print(detect_intent("im felling ssaad"))
