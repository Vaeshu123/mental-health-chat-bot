CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life",
    "self harm", "hurt myself", "no reason to live","harm myself"
]

def is_crisis(text):
    text = text.lower()
    return any(k in text for k in CRISIS_KEYWORDS)


from transformers import pipeline

classifier = pipeline("zero-shot-classification")

labels = ["self-harm intent", "emotional distress", "neutral"]

def zero_shot_detect(text):
    result = classifier(text, labels)
    return result["labels"]


print(is_crisis("im felling ssaad"))