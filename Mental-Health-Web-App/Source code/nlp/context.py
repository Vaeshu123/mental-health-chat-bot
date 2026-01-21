GRIEF_KEYWORDS = [
    "expired", "died", "passed away", "lost",
    "death", "no more", "gone forever","stressed","anxious"
]

def detect_context(text):
    text = text.lower()
    if any(word in text for word in GRIEF_KEYWORDS):
        return "grief"
    return "general"

print(detect_context("i am stressed"))