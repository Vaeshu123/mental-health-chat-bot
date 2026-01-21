from textblob import TextBlob

NEGATIVE_KEYWORDS = {
    "stress", "stressed", "stressful",
    "sad", "low", "down", "anxious",
    "overwhelmed", "tired", "burnt", "burned"
}

def get_mood(text):
    text_lower = text.lower()

    # 1. Keyword-based override (mental health specific)
    if any(word in text_lower for word in NEGATIVE_KEYWORDS):
        return "negative"

    # 2. Fallback to polarity
    polarity = TextBlob(text).sentiment.polarity
    print("Polarity:", polarity)

    if polarity < -0.1:
        return "negative"
    elif polarity > 0.1:
        return "positive"
    return "neutral"

print(get_mood("i do not which point in life is triggering this but feeling low and sad whole day"))