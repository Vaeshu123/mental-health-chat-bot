from flask import Flask, request, jsonify, render_template, session
from flask_session import Session
import string
import logging
from textblob import TextBlob
import uuid


from nlp.crisis import is_crisis
from nlp.intent import detect_intent
from nlp.context import detect_context
from nlp.prompt import SYSTEM_PROMPT
from responses.emergency import CRISIS_RESPONSE
from llama.client import query_llama

# ---------------- LOGGING SETUP ----------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------- APP SETUP ----------------
APP_BOOT_ID = str(uuid.uuid4())
 # change this on restart if needed
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# ---------------- CONSTANTS ----------------
EXERCISE_PHRASES = {
    "i want to try the exercise",
    "exercise",
    "grounding exercise"
}

TALK_MORE_PHRASES = {
    "talk more",
    "i want to talk more",
    "let's talk",
    "i would like to share",
    "i want to share",
    "i'd like to share"
}

IMPROVEMENT_PHRASES = {
    "i want to improve",
    "i want to get better",
    "i want help",
    "i want to feel better"
}

COPING_PHRASES = {
    "how to cope",
    "how do i cope",
    "how can i cope",
    "how to handle",
    "how to deal",
    "avoid anxiety",
    "reduce anxiety",
    "manage anxiety",
    "control anxiety"
}

AFFIRMATIONS = {"yes", "yeah", "yep", "sure", "ok", "okay"}
NEGATIONS = {"no", "nope", "nah", "not really", "not now"}

GREETINGS = {
    "hi", "hello", "hey",
    "good morning", "good afternoon", "good evening",
    "morning", "afternoon", "evening",
    "hi there", "hello there", "hey there"
}

NEGATIVE_MOODS = {"sad", "stressed", "anxious", "negative", "very_negative"}

DISTRESS_KEYWORDS = {
    "sad", "low", "down", "stressed", "stressful",
    "anxious", "overwhelmed", "tired", "exhausted",
    "burnt out", "burned out", "hopeless",
    "empty", "lonely", "heavy", "numb"
}

# ---------------- MOOD DETECTION ----------------
def get_mood(text):
    text_lower = text.lower()
    # keyword override
    if any(word in text_lower for word in DISTRESS_KEYWORDS):
        return "negative"
    # fallback to TextBlob polarity
    polarity = TextBlob(text).sentiment.polarity
    logging.debug(f"Polarity: {polarity}")
    if polarity <= -0.1:
        return "negative"
    elif polarity >= 0.2:
        return "positive"
    return "neutral"

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json["message"]
    normalized = user_input.lower().strip()
    normalized_no_punct = normalized.translate(
        str.maketrans("", "", string.punctuation)
    )

    # --------- INTENT & SAFETY ---------
    intent = detect_intent(user_input)
    print("intent.....",intent)
    print(is_crisis(user_input))
    if intent == "self-harm" or is_crisis(user_input):
        logging.warning("CRISIS DETECTED — emergency response returned")
        return jsonify({"reply": CRISIS_RESPONSE, "crisis": True})

    mood = get_mood(user_input)
    context = detect_context(user_input)

    logging.debug(f"DETECTED | intent={intent} | mood={mood} | context={context}")

    # --------- SESSION STATE ---------
    if ("conversation_state"not in session or session.get("app_boot_id") != APP_BOOT_ID):
        session["app_boot_id"] = APP_BOOT_ID

        session["conversation_state"] = {
            "mode": "idle",
            "current_activity": None,
            "exercise_step": 0,
            "last_option_offered": None,
            "pending_action": None,
            "intent_history": [],
            "disclosure_count": 0,
            "gratitude_active": False,
            "gratitude_completed": False,
            "gratitude_declined" : False,
            "history": []  # <-- ADD THIS
        }
        logging.debug("INITIALIZED NEW CONVERSATION STATE")

    state = session["conversation_state"]
    # history
    state["history"].append({
        "role": "user",
        "content": user_input
    })

    # Optional: limit history size
    state["history"] = state["history"][-10:]

    logging.debug(
        f"STATE BEFORE | mode={state['mode']} | pending_action={state['pending_action']} | "
        f"gratitude_active={state['gratitude_active']} | "
        f"gratitude_completed={state['gratitude_completed']} | "
        f"disclosure_count={state['disclosure_count']}"
    )

    state.setdefault("pending_action", None)
    state.setdefault("disclosure_count", 0)
    state.setdefault("gratitude_active", False)
    state.setdefault("gratitude_completed", False)
    state.setdefault("history", [])

    # --------- TRACK DISCLOSURE ---------
    if mood=='negative':
        print('I am here in this block............................')
        print(state['disclosure_count'])
        state["disclosure_count"] += 1
        print(state['disclosure_count'])

        logging.debug(
            f"NEGATIVE MOOD TRACKED | mood={mood} | disclosure_count={state['disclosure_count']}"
        )

    # --------- GRATITUDE COMPLETION: "done" ---------
    if normalized == "done" and state["gratitude_active"]:
        logging.debug("GRATITUDE COMPLETED VIA 'done'")
        state["gratitude_active"] = False
        state["gratitude_completed"] = True
        state["disclosure_count"] = 0
        session["conversation_state"] = state

        reply_text = """Thank you for trying that.Even taking a brief pause like this can help.
                Would you like to talk about how you’re feeling now,
                or try another coping strategy?"""

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- GRATITUDE COMPLETION: text response ---------
    if state["gratitude_active"]:
        logging.debug("GRATITUDE COMPLETED VIA TEXT RESPONSE")
        state["gratitude_active"] = False
        state["gratitude_completed"] = True
        session["conversation_state"] = state
        reply_text = """That’s really meaningful. Holding onto something like that can matter a lot when things feel heavy.
                How do you feel after naming that?"""  

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})


    # --------- HANDLE PENDING ACTIONS FIRST ---------
    if state["pending_action"]:
        action = state["pending_action"]

        # gratitude exercise
        if action == "gratitude_exercise":
            if normalized in AFFIRMATIONS:
                state["pending_action"] = None
                state["gratitude_active"] = True
                #session["conversation_state"] = state

                reply_text = (
                    "Great! Take a moment and think of one small thing today "
                    "that you feel grateful for."
                    "You can type it here or say 'done' when ready."
                )  # whatever reply you are sending

                session["conversation_state"] = state

                state["history"].append({
                    "role": "assistant",
                    "content": reply_text
                })
                session["conversation_state"] = state
                return jsonify({"reply": reply_text, "crisis": False})

            elif normalized in NEGATIONS:
                state["pending_action"] = None
                state["mode"] = "listening"
                state["gratitude_declined"] = True
                reply_text = """That’s completely okay.We don’t have to do that.
                    I’m here if you’d rather talk or just take things slowly."""

                state["history"].append({
                    "role": "assistant",
                    "content": reply_text
                })
                #session["conversation_state"] = state
                state["gratitude_active"] = False
                return jsonify({"reply": reply_text, "crisis": False})

            else:
                # user declined
                state["pending_action"] = None

                reply_text = (
                    "That’s okay—just let me know if you want to try it or skip it.\n"
                    "You can say 'yes' or 'no'."
                )

                session["conversation_state"] = state
                return jsonify({"reply": reply_text, "crisis": False})

    # --------- TALK MODE ---------
    if normalized in TALK_MORE_PHRASES:
        state["mode"] = "listening"
        state["pending_action"] = None
        session["conversation_state"] = state
        reply_text = """I'm here and listening. Please share whatever feels comfortable.""" 

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- IMPROVEMENT / COPING ---------
    if any(p in normalized for p in IMPROVEMENT_PHRASES | COPING_PHRASES):
        state["mode"] = "coping"
        session["conversation_state"] = state
        reply_text = """I’m really glad you said that. Wanting to improve is an important step.
                Right now, what would help most?
                1. reducing stress
                2. understanding what’s weighing on you
                3. rebuilding confidence"""  # whatever reply you are sending

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- EXERCISE REQUEST ---------
    if any(p in normalized for p in EXERCISE_PHRASES):
        state["pending_action"] = "grounding_exercise"
        reply_text = "Would you like to start a short grounding exercise now?"
        state["history"].append({"role": "assistant", "content": reply_text})
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- HANDLE CONFIRMATION FIRST ---------
    if state.get("pending_action") == "grounding_exercise":

        # YES → start exercise
        if normalized in AFFIRMATIONS:
            state["pending_action"] = None
            state["mode"] = "exercise"
            state["exercise_step"] = 1

            reply_text = (
                "Alright, let's begin.\n"
                "Sit comfortably and relax your shoulders.\n"
                "Type 'yes' when you're ready."
            )
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        # NO → cancel exercise
        elif normalized in NEGATIONS:
            state["pending_action"] = None
            state["mode"] = "listening"
            state["exercise_step"] = 0

            reply_text = (
                "That’s completely okay. We don’t have to do that.\n"
                "If music helps you, go ahead and listen. I’m here if you want to talk."
            )
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        # unclear
        else:
            reply_text = "You can say 'yes' to start, or 'no' to skip."
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

    # --------- EXERCISE MODE ---------
    if state["mode"] == "exercise":

        if state["exercise_step"] == 1 and normalized in AFFIRMATIONS:
            state["exercise_step"] = 2
            reply_text = (
                "Breathe in for 4 seconds.\n"
                "Hold for 2 seconds.\n"
                "Breathe out for 6 seconds.\n"
                "Type 'yes' when ready."
            )
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        if state["exercise_step"] == 2 and normalized in AFFIRMATIONS:
            state["mode"] = "idle"
            state["exercise_step"] = 0
            reply_text = "Well done. Would you like to talk about how you feel now?"
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        reply_text = "Take your time. Type 'yes' when ready."
        state["history"].append({"role": "assistant", "content": reply_text})
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- EXERCISE MODE ---------
    if state["mode"] == "exercise":

        if state["exercise_step"] == 1 and normalized in AFFIRMATIONS:
            state["exercise_step"] = 2

            reply_text = (
                "Breathe in through your nose for 4 seconds.\n"
                "Hold for 2 seconds.\n"
                "Exhale slowly through your mouth for 6 seconds.\n"
                "Type 'yes' when ready."
            )
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        if state["exercise_step"] == 2 and normalized in AFFIRMATIONS:
            state["mode"] = "idle"
            state["exercise_step"] = 0

            reply_text = (
                "Well done.\n"
                "Would you like to talk about how you feel now?"
            )
            state["history"].append({"role": "assistant", "content": reply_text})
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        reply_text = "Take your time. Type 'yes' when ready."
        state["history"].append({"role": "assistant", "content": reply_text})
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- GREETING ---------
    first_two_words = " ".join(normalized_no_punct.split()[:2])
    if any(first_two_words.startswith(g) for g in GREETINGS):
        session["conversation_state"] = state
        reply_text = "Hello! I'm a mental health support bot.How have you been feeling today?"  

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- GRATITUDE OFFER (after 2 negative disclosures) ---------
    if (
        state["disclosure_count"] >= 2
        and not state["gratitude_active"]
        and not state["gratitude_completed"]
        and not state["gratitude_declined"]
        and state["pending_action"] is None
        and state["mode"] != "exercise"
    ):
        state["pending_action"] = "gratitude_exercise"
        session["conversation_state"] = state
        logging.debug("GRATITUDE OFFERED (threshold reached)")
        reply_text = """It seems like things have been heavy lately.
            One gentle thing that can help is noticing something small you are grateful for.
                Would you like to try a short gratitude exercise now?"""  

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- DIRECT STRESS / DISTRESS HANDLER ---------
    if (
        intent in {"stress", "distress"}
        and mood in NEGATIVE_MOODS
        and state["mode"] == "idle"
    ):
        state["pending_action"] = "offer_talk_or_steady"
        session["conversation_state"] = state
        reply_text = """That sounds really stressful.
                Would you like to:"
                1. talk more about what's going on
                2. try something gentle to feel steadier"""  

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # --------- HANDLE user choice for stress/distress offer ---------
    if state["pending_action"] == "offer_talk_or_steady":
        state["pending_action"] = None
        if "talk" in normalized:
            state["mode"] = "listening"
            session["conversation_state"] = state
            reply_text = "I'm here. You can share whatever feels comfortable."  

            state["history"].append({
                "role": "assistant",
                "content": reply_text
            })
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

        if any(word in normalized for word in {"steady", "calm", "exercise", "help"}):
            state["pending_action"] = "grounding_exercise"
            session["conversation_state"] = state
            reply_text = "Okay. Would you like to try a short grounding exercise now?" 

            state["history"].append({
                "role": "assistant",
                "content": reply_text
            })
            session["conversation_state"] = state
            return jsonify({"reply": reply_text, "crisis": False})

    history_text = ""
    for msg in state["history"]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    # --------- LLM FALLBACK ---------
    prompt = f"""
{SYSTEM_PROMPT}

Conversation mode: {state['mode']}
Detected intent: {intent}
Detected mood: {mood}
Context: {context}
Conversation state: {state}

Conversation so far:
{history_text}

User message: {user_input}

Respond now:
"""
    reply_text = query_llama(prompt)

    session["conversation_state"] = state
    state["history"].append({
        "role": "assistant",
        "content": reply_text
    })
    session["conversation_state"] = state
    return jsonify({"reply":reply_text , "crisis": False})


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)