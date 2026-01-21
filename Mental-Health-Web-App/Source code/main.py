from datetime import datetime, date

import matplotlib
from flask import Flask, request, render_template, session, redirect,jsonify
import pandas as pd
import os

import pymysql

import matplotlib.pyplot as plt
matplotlib.use('agg')



import pickle
import re

import numpy
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from collections import defaultdict

from nlp.crisis import is_crisis
from nlp.intent import detect_intent
from nlp.context import detect_context
from nlp.prompt import SYSTEM_PROMPT
from responses.emergency import CRISIS_RESPONSE
from llama.client import query_llama


from flask_session import Session
import string
import logging
from textblob import TextBlob
import uuid


import torch
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

from ml.prediction import predict_percentage
conn = pymysql.connect(host="localhost", user="root", password="sai@54321", db="health")
cursor = conn.cursor()
app = Flask(__name__)
app.secret_key = "abc"
admin_username = "admin"
admin_password = "admin"

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
USER_PROFILE = APP_ROOT + "/static/user_profile_pictures/"



@app.route("/")
def index():
    return render_template("user_login.html")


@app.route("/admin_login")
def admin_login():
    return render_template("admin_login.html")


@app.route("/admin_login_action", methods=['post'])
def admin_login_action():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == admin_username and password == admin_password:
        session['role'] = 'admin'
        return redirect("/admin_home")
    else:
        return render_template("/message.html", message="Invalid Login Details")


def time_ago(created_at):
    now = datetime.now()
    diff = now - created_at

    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = diff.days
    weeks = days // 7

    if seconds < 60:
        return "just now"
    elif minutes < 60:
        return f"{int(minutes)} min ago"
    elif hours < 24:
        return f"{int(hours)} hr ago"
    elif days < 7:
        return f"{int(days)} day{'s' if days > 1 else ''} ago"
    elif weeks < 5:
        return f"{int(weeks)} week{'s' if weeks > 1 else ''} ago"
    else:
        return created_at.strftime("%b %d, %Y")

@app.route("/admin_home")
def admin_home():
    query = """
        SELECT p.post_id, p.description, p.privacy_type,
               p.user_id, p.created_at, u.name AS user_name
        FROM post p
        JOIN users u ON p.user_id = u.user_id
        ORDER BY p.created_at DESC
    """
    cursor.execute(query)
    posts = cursor.fetchall()

    post_data = []

    for post in posts:
        (
            post_id, description,
            privacy_type, user_id,
            created_at, user_name
        ) = post

        # ---- DistilBERT Prediction ----
        if description and description.strip():
            max_label, confidence = predict_percentage(description)
        else:
            max_label = "unknown"
            confidence = 0

        post_data.append({
            'post_id': post_id,
            'description': description,
            'user_id': user_id,
            'created_at': created_at,
            'created_at_str': created_at.strftime('%Y-%m-%d %I:%M:%S %p'),
            'time_ago': time_ago(created_at),
            'user_name': user_name,
            'mood_label': max_label,
            'confidence': confidence
        })

    return render_template("admin_home.html", posts=post_data)


@app.route("/user_login")
def user_login():
    return render_template("user_login.html")


@app.route("/user_register")
def user_register():
    return render_template("user_register.html")


@app.route("/user_registration_action",methods=['post'])
def user_registration_action():
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    address = request.form.get("address")
    password = request.form.get("password")
    gender = request.form.get("gender")
    profile_picture = request.files.get("profile_picture")
    path = USER_PROFILE + "" + profile_picture.filename
    profile_picture.save(path)
    count = cursor.execute("select * from users where email='" + str(email) + "' and phone='" + str(phone) + "'")
    if count > 0:
        return render_template("message.html", message="Duplicate Details Exist")
    else:
        cursor.execute(
            "insert into users(name,email, password, address, phone,gender,profile_picture,status) values('" + str(name) + "','" + str(
                email) + "','" + str(password) + "','" + str(address) + "','" + str(phone) + "','" + str(gender) + "','" + str(profile_picture.filename) + "','Not verified')")
        conn.commit()
        return render_template("message.html", message="User Registration Successfully")


@app.route("/user_login_action",methods=['post'])
def user_login_action():
    email = request.form.get("email")
    password = request.form.get("password")
    count = cursor.execute(
        "select * from users where email='" + str(email) + "' and password='" + str(password) + "'")
    if count > 0:
        user = cursor.fetchall()
        if user[0][8] == 'Not verified':
            return render_template("message.html", message="Your Account Not Verified")
        else:
            session['user_id'] = user[0][0]
            session['role'] = 'user'
            return redirect("/view_post")
    else:
        return render_template("message.html", message="invalid login details")


@app.route("/user_home")
def user_home():
    return render_template("user_home.html")


@app.route("/search_friends", methods=["GET", "POST"])
def search_friends():
    current_user_id = session.get("user_id")
    search_query = request.form.get("search", "")

    # Get all users excluding current user and already connected/requested ones
    query = """
        SELECT * FROM users 
        WHERE user_id != %s
        AND user_id NOT IN (
            SELECT receiver_id FROM friend_requests WHERE sender_id = %s
            UNION
            SELECT sender_id FROM friend_requests WHERE receiver_id = %s
        )
    """
    params = (current_user_id, current_user_id, current_user_id)

    if search_query:
        query = """
            SELECT * FROM users 
            WHERE user_id != %s
            AND user_id NOT IN (
                SELECT receiver_id FROM friend_requests WHERE sender_id = %s
                UNION
                SELECT sender_id FROM friend_requests WHERE receiver_id = %s
            )
            AND (name LIKE %s OR email LIKE %s)
        """
        params = (
            current_user_id,
            current_user_id,
            current_user_id,
            f"%{search_query}%",
            f"%{search_query}%"
        )

    cursor.execute(query, params)
    users = cursor.fetchall()

    cursor.execute("""
        SELECT receiver_id, friend_requests_id 
        FROM friend_requests 
        WHERE sender_id = %s AND status = 'pending'
    """, (current_user_id,))
    request_map = {row[0]: row[1] for row in cursor.fetchall()}

    return render_template("search_friends.html", users=users, request_map=request_map)


@app.route("/send_request/<int:user_id>")
def send_request(user_id):
    sender_id = session['user_id']
    cursor.execute("INSERT INTO friend_requests (sender_id, receiver_id, status) VALUES (%s, %s, 'pending')", (sender_id, user_id))
    conn.commit()
    return redirect("/search_friends")


@app.route("/cancel_request/<int:request_id>")
def cancel_request(request_id):
    cursor.execute("DELETE FROM friend_requests WHERE friend_requests_id = %s", (request_id,))
    conn.commit()
    return redirect("/search_friends")


@app.route("/requests")
def requests():
    current_user = session['user_id']

    # Get all friend requests where the user is sender or receiver
    cursor.execute("""
        SELECT * FROM friend_requests 
        WHERE sender_id = %s OR receiver_id = %s
    """, (current_user, current_user))
    friend_requests = cursor.fetchall()

    return render_template(
        "requests.html",
        requests=friend_requests,
        current_user=current_user,
        get_user_by_id=get_user_by_id
    )


@app.route("/send_request_again/<int:other_user_id>")
def send_request_again(other_user_id):
    current_user = session['user_id']

    # Clean old request if exists
    cursor.execute("""
        DELETE FROM friend_requests 
        WHERE (sender_id=%s AND receiver_id=%s) 
           OR (sender_id=%s AND receiver_id=%s)
    """, (current_user, other_user_id, other_user_id, current_user))

    # Insert new request
    cursor.execute("""
        INSERT INTO friend_requests(sender_id, receiver_id, status)
        VALUES (%s, %s, 'pending')
    """, (current_user, other_user_id))

    conn.commit()
    return redirect("/requests")


@app.route("/unfriend/<int:request_id>")
def unfriend(request_id):
    cursor.execute("UPDATE friend_requests SET status='unfriended' WHERE friend_requests_id=%s", (request_id,))
    conn.commit()
    return redirect("/requests")

@app.route("/block/<int:request_id>")
def block(request_id):
    cursor.execute("UPDATE friend_requests SET status='blocked' WHERE friend_requests_id=%s", (request_id,))
    conn.commit()
    return redirect("/requests")

@app.route("/unblock/<int:request_id>")
def unblock(request_id):
    cursor.execute("UPDATE friend_requests SET status='accepted' WHERE friend_requests_id=%s", (request_id,))
    conn.commit()
    return redirect("/requests")




def get_user_by_id(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()


@app.route("/accept_request/<int:request_id>")
def accept_request(request_id):
    cursor.execute("UPDATE friend_requests SET status = 'accepted' WHERE friend_requests_id = %s", (request_id,))
    conn.commit()
    return redirect("/requests")

@app.route("/reject_request/<int:request_id>")
def reject_request(request_id):
    cursor.execute("UPDATE friend_requests SET status = 'rejected' WHERE friend_requests_id = %s", (request_id,))
    conn.commit()
    return redirect("/requests")

@app.route("/cancel_request/<int:request_id>")
def cancel_friend_request(request_id):
    cursor.execute("DELETE FROM friend_requests WHERE friend_requests_id = %s", (request_id,))
    conn.commit()
    return redirect("/requests")




@app.route("/logout")
def logout():
    session.clear()
    return render_template("index.html")


@app.route("/post")
def post():
    user_id = str(session['user_id'])

    query = f"""
        SELECT * FROM post WHERE 
        (
            (privacy_type = 'private' AND user_id = '{user_id}')
            OR (privacy_type = 'public' AND user_id = '{user_id}')
            OR (
                privacy_type = 'public' AND (
                    user_id IN (
                        SELECT sender_id FROM friend_requests 
                        WHERE receiver_id = '{user_id}' AND status = 'accepted'
                    )
                    OR user_id IN (
                        SELECT receiver_id FROM friend_requests 
                        WHERE sender_id = '{user_id}' AND status = 'accepted'
                    )
                )
            )
        )
    """

    cursor.execute(query)
    posts = cursor.fetchall()

    return render_template("post.html", posts=posts,
                           get_user_id_in_post=get_user_id_in_post,
                           str=str,
                           get_likes_count_by_post_id=get_likes_count_by_post_id,
                           get_comment_count_by_post_id=get_comment_count_by_post_id,
                           get_share_count_by_post_id=get_share_count_by_post_id,
                           is_user_liked_the_post=is_user_liked_the_post)



@app.route("/add_post")
def add_post():
    return render_template("add_post.html")
@app.route("/add_post_action", methods=['POST'])
def add_post_action():
    description = request.form.get("description")
    privacy_type = request.form.get("privacy_type")
    user_id = session['user_id']

    now = datetime.now()
    query = """
        INSERT INTO post(description, privacy_type, user_id,created_at)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (description, privacy_type, user_id,now))
    conn.commit()

    return redirect("/view_post")  # Redirect to post viewing page after submission


@app.route("/view_post")
def view_post():
    user_id = str(session['user_id'])

    query = """
        SELECT * FROM post 
        WHERE 
            user_id = %s
            OR (
                privacy_type = 'public'
                AND (
                    user_id IN (
                        SELECT sender_id FROM friend_requests 
                        WHERE receiver_id = %s AND status = 'accepted'
                    )
                    OR user_id IN (
                        SELECT receiver_id FROM friend_requests 
                        WHERE sender_id = %s AND status = 'accepted'
                    )
                    OR user_id != %s
                )
            )
        ORDER BY created_at DESC
    """
    cursor.execute(query, (user_id, user_id, user_id, user_id))
    posts = cursor.fetchall()

    # Attach 'time_ago' to each post
    post_data = []
    for post in posts:
        created_at = post[7]  # index of created_at in your SELECT *
        post_dict = dict(
            post_id=post[0],
            description=post[4],
            privacy_type=post[5],
            user_id=post[6],
            created_at=post[7],
            time_ago=time_ago(post[7])
        )
        post_data.append(post_dict)

    return render_template("view_post.html",
                           posts=post_data,
                           get_user_id_in_post=get_user_id_in_post,
                           get_likes_count_by_post_id=get_likes_count_by_post_id,
                           get_comment_count_by_post_id=get_comment_count_by_post_id,
                           get_share_count_by_post_id=get_share_count_by_post_id,
                           is_user_liked_the_post=is_user_liked_the_post)

@app.route("/add_comment")
def add_comment():
    post_id = request.args.get('post_id')
    comment = request.args.get('comment')
    user_id = session['user_id']
    cursor.execute("INSERT INTO comment(comment, user_id, post_id) VALUES (%s, %s, %s)", (comment, user_id, post_id))
    conn.commit()
    return redirect("/view_post")


@app.route("/add_like")
def add_like():
    post_id = request.args.get('post_id')
    user_id = session['user_id']

    cursor.execute("SELECT * FROM likes WHERE post_id=%s AND user_id=%s", (post_id, user_id))
    if cursor.rowcount > 0:
        cursor.execute("DELETE FROM likes WHERE post_id=%s AND user_id=%s", (post_id, user_id))
    else:
        cursor.execute("INSERT INTO likes(user_id, post_id) VALUES (%s, %s)", (user_id, post_id))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM likes WHERE post_id=%s", (post_id,))
    count = cursor.fetchone()[0]

    return render_template("add_like.html", count=count, post_id=post_id, is_user_liked_the_post=is_user_liked_the_post)


@app.route("/get_comments")
def get_comments():
    post_id = request.args.get('post_id')
    cursor.execute("SELECT * FROM comment WHERE post_id=%s", (post_id,))
    comments = cursor.fetchall()
    return render_template("get_comments.html", comments=comments, post_id=post_id, get_user_id_in_comment=get_user_id_in_comment)


def get_user_id_in_post(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()

def get_user_id_in_comment(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()

def get_likes_count_by_post_id(post_id):
    cursor.execute("SELECT COUNT(*) FROM likes WHERE post_id = %s", (post_id,))
    return cursor.fetchone()[0]

def get_comment_count_by_post_id(post_id):
    cursor.execute("SELECT COUNT(*) FROM comment WHERE post_id = %s", (post_id,))
    return cursor.fetchone()[0]

def get_share_count_by_post_id(post_id):
    cursor.execute("SELECT COUNT(*) FROM share WHERE post_id = %s", (post_id,))
    return cursor.fetchone()[0]

def is_user_liked_the_post(post_id):
    cursor.execute("SELECT * FROM likes WHERE post_id = %s AND user_id = %s", (post_id, session['user_id']))
    return cursor.rowcount > 0


@app.route("/home")
def home():
    user_id = session['user_id']
    print("hiii")
    print("Session User ID:", session.get('user_id'))

    query = """
        SELECT * FROM users 
        WHERE user_id IN (
            SELECT receiver_id FROM friend_requests 
            WHERE sender_id=%s AND status != 'pending'
        ) OR user_id IN (
            SELECT sender_id FROM friend_requests 
            WHERE receiver_id=%s AND status != 'pending'
        )
    """
    cursor.execute(query, (user_id, user_id))
    friends = cursor.fetchall()
    print(friends)
    return render_template("home.html", friends=friends)




@app.route("/get_messages")
def get_messages():
    user_id = session['user_id']
    other_id = request.args.get('other_customer_id')
    query = """
        SELECT * FROM chat 
        WHERE (sender_id=%s AND receiver_id=%s) 
           OR (sender_id=%s AND receiver_id=%s)
        ORDER BY date ASC
    """
    cursor.execute(query, (user_id, other_id, other_id, user_id))
    messages = cursor.fetchall()
    return {"messages": messages}


@app.route("/get_message")
def get_message():
    user_id = session['user_id']
    other_id = request.args.get('other_customer_id')

    conn2 = pymysql.connect(host="localhost", user="root", password="root", db="health", cursorclass=pymysql.cursors.DictCursor)
    cursor2 = conn2.cursor()

    query = """
        SELECT * FROM chat 
        WHERE (sender_id=%s AND receiver_id=%s AND isSenderRead='unread') 
           OR (sender_id=%s AND receiver_id=%s AND isReceiverRead='unread')
    """
    cursor2.execute(query, (user_id, other_id, other_id, user_id))
    messages = cursor2.fetchall()

    for message in messages:
        if message['sender_id'] == user_id:
            cursor2.execute("UPDATE chat SET isSenderRead='read' WHERE chat_id=%s", (message['chat_id'],))
        elif message['receiver_id'] == user_id:
            cursor2.execute("UPDATE chat SET isReceiverRead='read' WHERE chat_id=%s", (message['chat_id'],))
        conn2.commit()

    return {"messages": messages}


@app.route("/send_messages")
def send_messages():
    user_id = session['user_id']
    other_id = request.args.get('other_customer_id')
    message = request.args.get('message')

    query = """
        INSERT INTO chat (sender_id, receiver_id, message, isSenderRead, isReceiverRead, date)
        VALUES (%s, %s, %s, 'unread', 'unread', NOW())
    """
    cursor.execute(query, (user_id, other_id, message))
    conn.commit()
    return {"status": "ok"}


@app.route("/set_as_read_receiver")
def set_as_read_receiver():
    user_id = session['user_id']
    other_id = request.args.get('other_customer_id')

    conn2 = pymysql.connect(host="localhost", user="root", password="root", db="health")
    cursor2 = conn2.cursor()
    query = """
        UPDATE chat SET isReceiverRead='read' 
        WHERE sender_id=%s AND receiver_id=%s
    """
    cursor2.execute(query, (other_id, user_id))
    conn2.commit()
    return {"status": "ok"}


@app.route("/set_as_read_sender")
def set_as_read_sender():
    user_id = session['user_id']
    other_id = request.args.get('other_customer_id')

    conn2 = pymysql.connect(host="localhost", user="root", password="root", db="health")
    cursor2 = conn2.cursor()
    query = """
        UPDATE chat SET isSenderRead='read' 
        WHERE sender_id=%s AND receiver_id=%s
    """
    cursor2.execute(query, (user_id, other_id))
    conn2.commit()
    return {"status": "ok"}


@app.route("/view_verify_users")
def view_verify_users():
    cursor.execute("select * from users")
    users = cursor.fetchall()
    return render_template("view_verify_users.html",users=users)

@app.route("/verify_user/<int:user_id>")
def verify_user(user_id):
    cursor.execute("UPDATE users SET status='verified' WHERE user_id=%s", (user_id,))
    conn.commit()
    return redirect("/view_verify_users")

@app.route("/deverify_user/<int:user_id>")
def deverify_user(user_id):
    cursor.execute("UPDATE users SET status='Not verified' WHERE user_id=%s", (user_id,))
    conn.commit()
    return redirect("/view_verify_users")


# Load model




# ---------------- APP SETUP ----------------
APP_BOOT_ID = str(uuid.uuid4())
 # change this on restart if needed

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


@app.route("/bot")
def bot():
    return render_template("bot.html")


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
                3. rebuilding confidence"""  

        state["history"].append({
            "role": "assistant",
            "content": reply_text
        })
        session["conversation_state"] = state
        return jsonify({"reply": reply_text, "crisis": False})

    # llm code of grounding
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


if __name__ == "__main__":
    app.run(debug=True)