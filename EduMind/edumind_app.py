import os
import re
import random
import sqlite3
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

# ==========================================================
# EDUMIND AI - SMART STUDENT WORKSPACE
# Single-file Streamlit college project
# ==========================================================

st.set_page_config(
    page_title="EduMind AI | Student Workspace",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "edumind.db"

# ------------------------- DESIGN -------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

.stApp {
    background: #f6f7fc;
    font-family: 'DM Sans', sans-serif;
}
.block-container {
    padding-top: 1.5rem;
    max-width: 1450px;
}
h1, h2, h3 {
    font-family: 'Manrope', sans-serif;
    color: #202448;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#191c3b,#30295e);
}
section[data-testid="stSidebar"] * {
    color: #ffffff;
}
.hero {
    padding: 32px;
    border-radius: 24px;
    background: linear-gradient(120deg,#222449,#5848b8,#8b7df4);
    color: white;
    margin-bottom: 24px;
}
.hero h1 {
    color: white;
    font-size: 2.35rem;
}
.hero p {
    color: #e9e7ff;
    font-size: 1.05rem;
}
.card {
    background: white;
    padding: 21px;
    border: 1px solid #e8eaf4;
    border-radius: 18px;
    margin-bottom: 14px;
    box-shadow: 0 5px 20px rgba(30,40,90,.035);
}
.card h3 {
    margin-top: 0;
}
.stat {
    background: white;
    border: 1px solid #e7e9f3;
    border-radius: 17px;
    padding: 18px;
    min-height: 115px;
}
.stat-label {
    color: #7b819b;
    font-size: .88rem;
}
.stat-value {
    color: #5145b5;
    font-size: 1.8rem;
    font-weight: 800;
    margin-top: 8px;
}
div.stButton > button {
    border-radius: 11px;
    min-height: 42px;
    font-weight: 600;
}
div.stButton > button[kind="primary"] {
    background: #6555d9;
    color: white;
    border: none;
}
.tip {
    background: #edfaf4;
    border: 1px solid #d7f1e4;
    border-radius: 14px;
    padding: 16px;
}
</style>
""", unsafe_allow_html=True)


# ------------------------- DATABASE -------------------------

def connect():
    return sqlite3.connect(DB)


def initialize_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                subject TEXT,
                deadline TEXT,
                priority TEXT,
                completed INTEGER DEFAULT 0
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                minutes INTEGER,
                study_date TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                score INTEGER,
                total INTEGER,
                created_at TEXT
            )
        """)


initialize_database()


def get_tasks():
    with connect() as con:
        return pd.read_sql_query(
            "SELECT * FROM tasks ORDER BY deadline", con
        )


def get_sessions():
    with connect() as con:
        return pd.read_sql_query(
            "SELECT * FROM study_sessions ORDER BY id DESC", con
        )


def get_quiz_results():
    with connect() as con:
        return pd.read_sql_query(
            "SELECT * FROM quiz_results ORDER BY id DESC", con
        )


def add_task(title, subject, deadline, priority):
    with connect() as con:
        con.execute(
            """INSERT INTO tasks(title,subject,deadline,priority)
               VALUES(?,?,?,?)""",
            (title, subject, deadline.isoformat(), priority)
        )


# ------------------------- SESSION STATE -------------------------

defaults = {
    "chat_history": [],
    "notes": "",
    "quiz_questions": [],
    "quiz_submitted": False,
    "flash_index": 0,
    "show_flash_answer": False,
    "focus_subject": "Deep Learning"
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ------------------------- CHATBOT -------------------------

def split_sentences(text):
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", text)
        if s.strip()
    ]


def notes_search(question, notes):
    if not notes.strip():
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        sentences = split_sentences(notes)

        if not sentences:
            return []

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2)
        )

        matrix = vectorizer.fit_transform([question] + sentences)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()

        ranked = sorted(
            zip(sentences, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return [s for s, score in ranked[:5] if score > 0.04]

    except ValueError:
        return []


def format_answer(text, style):
    sentences = split_sentences(text)

    if style == "Short answer":
        return " ".join(sentences[:2]) if sentences else text[:400]

    if style == "Key points":
        return "\n".join(f"• {s}" for s in sentences)

    if style == "5-mark answer":
        points = "\n".join(
            f"{i}. {s}" for i, s in enumerate(sentences[:5], 1)
        )
        return (
            f"**Introduction / Definition**\n\n"
            f"{sentences[0] if sentences else text}\n\n"
            f"**Main points**\n\n{points}\n\n"
            f"**Conclusion**\n\n"
            "Thus, the concept is important in its practical application."
        )

    if style == "10-mark answer":
        points = "\n".join(
            f"{i}. {s}" for i, s in enumerate(sentences, 1)
        )
        return (
            f"**Introduction**\n\n{text}\n\n"
            f"**Detailed explanation**\n\n{points}\n\n"
            f"**Conclusion**\n\n"
            "In conclusion, the concept can be understood through "
            "its definition, working and applications."
        )

    if style == "Simple Hinglish":
        return (
            text
            + "\n\n**Easy explanation:** Is concept ko pehle basic "
            "meaning se samjho, phir example aur important points revise karo."
        )

    if style == "Step-by-step":
        return "\n".join(
            f"**Step {i}:** {s}"
            for i, s in enumerate(sentences, 1)
        )

    return text


def offline_answer(question, notes, style):
    q = question.lower().strip()

    matches = notes_search(question, notes)

    if matches:
        answer = "\n\n".join(matches)
        return format_answer(answer, style), "Uploaded notes"

    study_guide = {
        "ann": (
            "Artificial Neural Network (ANN) is a machine-learning model "
            "inspired by biological neurons. It contains input, hidden and "
            "output layers. It learns by adjusting weights and biases to "
            "reduce prediction error."
        ),
        "bilstm": (
            "Bidirectional Long Short-Term Memory (BiLSTM) is a neural "
            "network that processes sequence data in forward and backward "
            "directions. It can use context from both earlier and later "
            "words for text classification."
        ),
        "lstm": (
            "Long Short-Term Memory (LSTM) is a type of recurrent neural "
            "network. It uses input, forget and output gates to control "
            "information flow and learn patterns in sequence data."
        ),
        "overfitting": (
            "Overfitting occurs when a machine-learning model learns the "
            "training data too closely and performs poorly on unseen data. "
            "Dropout, regularization and more training data can help reduce it."
        ),
        "deep learning": (
            "Deep learning is a subset of machine learning that uses neural "
            "networks with multiple layers. Common architectures include ANN, "
            "CNN, RNN, LSTM and Transformers."
        ),
        "machine learning": (
            "Machine learning enables computers to learn patterns from data. "
            "Its major types are supervised learning, unsupervised learning "
            "and reinforcement learning."
        ),
        "python": (
            "Python is a high-level programming language used for web "
            "development, automation, data analysis and artificial "
            "intelligence. Popular libraries include NumPy, pandas and PyTorch."
        ),
        "sql": (
            "SQL stands for Structured Query Language. It is used to create, "
            "retrieve, update and delete data in relational databases. "
            "Common commands include SELECT, INSERT, UPDATE and DELETE."
        ),
        "iot": (
            "The Internet of Things connects physical devices using sensors, "
            "software and networks. A typical IoT system collects data, "
            "transfers it to a platform and uses it for monitoring or action."
        ),
        "normalization": (
            "Database normalization organizes tables to reduce duplicate "
            "data and update anomalies. Common normal forms include 1NF, "
            "2NF and 3NF."
        )
    }

    for term, explanation in study_guide.items():
        if term in q:
            return format_answer(explanation, style), "Offline study guide"

    if any(word in q for word in ["hello", "hi", "hey"]):
        return (
            "Hey! 👋 I am EduMind AI, your student study companion. "
            "Ask a concept, upload notes or request a short answer, "
            "key points, an exam answer or a step-by-step explanation."
        ), "EduMind"

    if any(word in q for word in ["plan", "timetable", "schedule"]):
        answer = (
            "1. Choose two priority topics.\n"
            "2. Study for 25 minutes.\n"
            "3. Take a 5-minute break.\n"
            "4. Practise questions for 20 minutes.\n"
            "5. Review mistakes and revise them tomorrow."
        )
        return format_answer(answer, style), "Study planner"

    return (
        "I couldn't find a reliable answer in the uploaded notes or my "
        "built-in study guide. Try uploading relevant notes, adding more "
        "context, or connecting an AI API for general academic questions."
    ), "Offline demo"


def chatbot_answer(question, style):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are EduMind AI, a helpful academic assistant. "
                        "Explain concepts accurately, give examples, and "
                        "follow the requested answer format. Use simple "
                        "Hinglish when requested. Do not invent sources."
                    )
                }
            ]

            notes = st.session_state["notes"]

            if notes:
                messages.append({
                    "role": "system",
                    "content": "Student's notes:\n" + notes[:12000]
                })

            for item in st.session_state["chat_history"][-8:]:
                if item["role"] in ("user", "assistant"):
                    messages.append({
                        "role": item["role"],
                        "content": item["content"][:4000]
                    })

            messages.append({
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Requested format: {style}"
                )
            })

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.5
            )

            return response.choices[0].message.content, "AI model"

        except Exception:
            return offline_answer(
                question, st.session_state["notes"], style
            )

    return offline_answer(question, st.session_state["notes"], style)


# ------------------------- SIDEBAR -------------------------

with st.sidebar:
    st.markdown("# 🎓 EduMind AI")
    st.caption("YOUR PERSONAL STUDY WORKSPACE")
    st.divider()

    pages = [
        "🏠 Dashboard",
        "💬 Study Chat",
        "🧠 Quiz & Flashcards",
        "🗓️ Assignments",
        "📈 My Progress",
        "🛠️ Student Toolkit"
    ]

    page = st.radio("NAVIGATION", pages)

    st.divider()

    st.markdown("### 🎯 Today's focus")

    st.session_state["focus_subject"] = st.text_input(
        "Subject",
        value=st.session_state["focus_subject"]
    )

    st.caption(
        "Assistant mode: "
        + (
            "AI connected"
            if os.getenv("OPENAI_API_KEY")
            else "Offline demo"
        )
    )


# ------------------------- COMMON DATA -------------------------

tasks = get_tasks()
sessions = get_sessions()
quizzes = get_quiz_results()

completed = int(tasks["completed"].sum()) if not tasks.empty else 0
pending = len(tasks) - completed

study_minutes = (
    int(sessions["minutes"].sum())
    if not sessions.empty else 0
)

quiz_average = (
    round((quizzes["score"] / quizzes["total"] * 100).mean())
    if not quizzes.empty else 0
)


# ------------------------- DASHBOARD -------------------------

if page == "🏠 Dashboard":

    st.markdown("""
    <div class="hero">
        <h1>Make today count. ✨</h1>
        <p>Your personal learning space. Ask questions, practise concepts,
        organise deadlines and track your progress — all in one place.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    stats = [
        ("Pending tasks", pending),
        ("Study minutes", study_minutes),
        ("Quiz average", f"{quiz_average}%" if not quizzes.empty else "—"),
        ("Completed tasks", completed)
    ]

    for col, (label, value) in zip([c1, c2, c3, c4], stats):
        with col:
            st.markdown(
                f"""
                <div class="stat">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("")
    left, right = st.columns([1.5, 1])

    with left:
        st.markdown("""
        <div class="card">
            <h3>🚀 Your learning workspace</h3>
            Ask doubts, practise MCQs and organise assignments.
        </div>
        """, unsafe_allow_html=True)

        a, b, c = st.columns(3)

        with a:
            st.markdown("### 💬")
            st.markdown("**Ask AI**")
            if st.button("Open Study Chat", use_container_width=True):
                st.session_state["page_navigation"] = "💬 Study Chat"
                st.info("Choose Study Chat from the sidebar.")

        with b:
            st.markdown("### 🧠")
            st.markdown("**Practise**")
            if st.button("Open Quiz", use_container_width=True):
                st.info("Choose Quiz & Flashcards from the sidebar.")

        with c:
            st.markdown("### 🗓️")
            st.markdown("**Plan tasks**")
            if st.button("Open Assignments", use_container_width=True):
                st.info("Choose Assignments from the sidebar.")

        st.markdown("### 📅 Upcoming assignments")

        if tasks.empty:
            st.info("No assignments yet. Add your first task!")
        else:
            for _, task in tasks[tasks["completed"] == 0].head(5).iterrows():
                st.markdown(
                    f"""
                    <div class="card">
                        <b>{task['title']}</b><br>
                        <span style="color:#777">
                        {task['subject']} · Due {task['deadline']}
                        · {task['priority']} priority
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    with right:
        st.markdown("""
        <div class="card">
            <h3>🌱 Your daily reminder</h3>
            You don't need a perfect day. You need a start.
        </div>
        <div class="tip">
            <b>Try a focus sprint</b><br>
            Study for 25 minutes, take a 5-minute break,
            then recall three important points.
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        st.markdown("### 📊 Activity snapshot")
        st.metric("Assignments", len(tasks))
        st.metric("Study sessions", len(sessions))
        st.metric("Quiz attempts", len(quizzes))


# ------------------------- STUDY CHAT -------------------------

elif page == "💬 Study Chat":

    st.markdown("""
    <div class="hero">
        <h1>Ask. Understand. Improve. 💬</h1>
        <p>Ask academic questions and customise the answer to your needs.
        Request key points, exam answers or simple explanations.</p>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.6, 1])

    with right:
        st.markdown("""
        <div class="card">
            <h3>🎛️ Answer preferences</h3>
            Choose how you want your answer.
        </div>
        """, unsafe_allow_html=True)

        style = st.selectbox(
            "Answer format",
            [
                "Detailed explanation",
                "Short answer",
                "Key points",
                "5-mark answer",
                "10-mark answer",
                "Simple Hinglish",
                "Step-by-step"
            ]
        )

        st.markdown("### 📎 Upload study notes")

        uploaded = st.file_uploader(
            "Upload a TXT file",
            type=["txt"]
        )

        if uploaded:
            st.session_state["notes"] = uploaded.getvalue().decode(
                "utf-8", errors="replace"
            )
            st.success("Your notes are ready!")

        if st.session_state["notes"]:
            st.caption(
                f"{len(st.session_state['notes'].split())} words loaded."
            )

            if st.button("Remove notes"):
                st.session_state["notes"] = ""
                st.rerun()

        st.markdown("""
        <div class="card">
            <b>Try asking:</b><br><br>
            • Explain ANN in simple language<br>
            • Make it a 5-mark answer<br>
            • Give important points<br>
            • Explain step by step<br>
            • Give an example
        </div>
        """, unsafe_allow_html=True)

    with left:
        st.markdown("### 💬 Your conversation")

        if st.button("🗑️ Clear conversation"):
            st.session_state["chat_history"] = []
            st.rerun()

        for message in st.session_state["chat_history"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input(
            "Ask a question or request a change to your answer..."
        )

        if question:
            st.session_state["chat_history"].append({
                "role": "user",
                "content": question
            })

            q = question.lower()
            previous = next(
                (
                    m["content"]
                    for m in reversed(st.session_state["chat_history"][:-1])
                    if m["role"] == "assistant"
                ),
                ""
            )

            reformat_words = [
                "short karo", "make it short", "shorter",
                "in points", "key points", "5 mark", "5-mark",
                "10 mark", "10-mark", "hinglish", "step by step",
                "simpler", "bullet points", "detail mein"
            ]

            if previous and any(word in q for word in reformat_words):
                new_style = style

                if "short" in q:
                    new_style = "Short answer"
                elif "point" in q or "bullet" in q:
                    new_style = "Key points"
                elif "5" in q and "mark" in q:
                    new_style = "5-mark answer"
                elif "10" in q and "mark" in q:
                    new_style = "10-mark answer"
                elif "hinglish" in q or "simpler" in q:
                    new_style = "Simple Hinglish"
                elif "step" in q:
                    new_style = "Step-by-step"

                answer = format_answer(previous, new_style)
                source = "Reformatted previous answer"

            else:
                with st.spinner("EduMind is thinking..."):
                    answer, source = chatbot_answer(question, style)

            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": answer
            })

            st.rerun()

    st.caption(
        "Without an API key, answers use uploaded notes and the offline "
        "study guide. With an API key, the AI provider generates answers."
    )


# ------------------------- QUIZ & FLASHCARDS -------------------------

elif page == "🧠 Quiz & Flashcards":

    st.markdown("""
    <div class="hero">
        <h1>Practise to remember. 🧠</h1>
        <p>Use active recall, quick quizzes and flashcards to strengthen
        your understanding.</p>
    </div>
    """, unsafe_allow_html=True)

    quiz_bank = [
        {
            "topic": "Deep Learning",
            "q": "Which activation function is commonly used in hidden layers?",
            "options": ["ReLU", "SQL", "HTML", "CSV"],
            "answer": "ReLU",
            "why": "ReLU returns max(0, x) and adds non-linearity."
        },
        {
            "topic": "Deep Learning",
            "q": "What does dropout help reduce?",
            "options": ["Overfitting", "Screen size", "File format", "Latency always"],
            "answer": "Overfitting",
            "why": "Dropout helps improve generalisation during training."
        },
        {
            "topic": "Python",
            "q": "Which library is used for tabular data?",
            "options": ["pandas", "Pygame", "Tkinter only", "Turtle only"],
            "answer": "pandas",
            "why": "pandas provides DataFrame and Series."
        },
        {
            "topic": "Database",
            "q": "Which command retrieves records?",
            "options": ["SELECT", "DROP", "ALTER", "GRANT"],
            "answer": "SELECT",
            "why": "SELECT retrieves data from tables."
        },
        {
            "topic": "IoT",
            "q": "What is the main role of a sensor?",
            "options": [
                "Measure physical values",
                "Compile Python",
                "Design slides",
                "Create database keys"
            ],
            "answer": "Measure physical values",
            "why": "Sensors measure values such as temperature and humidity."
        },
        {
            "topic": "Machine Learning",
            "q": "Which type uses labelled data?",
            "options": [
                "Supervised learning",
                "Unsupervised learning",
                "Random browsing",
                "Manual formatting"
            ],
            "answer": "Supervised learning",
            "why": "Supervised learning learns from labelled examples."
        },
        {
            "topic": "Python",
            "q": "Which keyword defines a function?",
            "options": ["def", "func", "define", "method"],
            "answer": "def",
            "why": "Python uses def to declare a function."
        },
        {
            "topic": "Database",
            "q": "Which key uniquely identifies a row?",
            "options": ["Primary key", "Comment", "Foreign label", "Sort only"],
            "answer": "Primary key",
            "why": "A primary key uniquely identifies a record."
        }
    ]

    quiz_tab, flash_tab = st.tabs(["📝 Quick Quiz", "🃏 Flashcards"])

    with quiz_tab:
        topic = st.selectbox(
            "Choose a topic",
            ["All topics", "Deep Learning", "Python", "Database", "IoT",
             "Machine Learning"]
        )

        available = [
            item for item in quiz_bank
            if topic == "All topics" or item["topic"] == topic
        ]

        if st.button("🎲 Generate quiz", type="primary"):
            st.session_state["quiz_questions"] = random.sample(
                available, min(5, len(available))
            )
            st.session_state["quiz_submitted"] = False

        questions = st.session_state["quiz_questions"]

        if questions:
            with st.form("quiz_form"):
                answers = {}

                for i, item in enumerate(questions):
                    st.markdown(f"**Q{i + 1}. {item['q']}**")
                    answers[str(i)] = st.radio(
                        "Choose an answer",
                        item["options"],
                        index=None,
                        key=f"answer_{i}",
                        label_visibility="collapsed"
                    )
                    st.divider()

                submitted = st.form_submit_button(
                    "Check my answers",
                    type="primary"
                )

            if submitted:
                score = sum(
                    answers[str(i)] == item["answer"]
                    for i, item in enumerate(questions)
                )

                with connect() as con:
                    con.execute(
                        """INSERT INTO quiz_results
                           (topic,score,total,created_at)
                           VALUES(?,?,?,?)""",
                        (
                            topic,
                            score,
                            len(questions),
                            datetime.now().isoformat(timespec="seconds")
                        )
                    )

                st.session_state["quiz_result"] = {
                    "score": score,
                    "total": len(questions),
                    "answers": answers,
                    "questions": questions
                }
                st.session_state["quiz_submitted"] = True

            if st.session_state["quiz_submitted"]:
                result = st.session_state["quiz_result"]

                st.success(
                    f"Your score: {result['score']} / {result['total']}"
                )

                for i, item in enumerate(result["questions"]):
                    correct = item["answer"]
                    picked = result["answers"].get(str(i))

                    st.markdown(
                        f"**Q{i+1}. Correct answer: {correct}**"
                    )
                    st.caption(
                        ("✅ Correct" if picked == correct else "❌ Incorrect")
                        + " — " + item["why"]
                    )

    with flash_tab:
        cards = [
            (
                "ANN",
                "Artificial Neural Network",
                "A model made of connected artificial neurons that learns "
                "patterns by adjusting weights."
            ),
            (
                "Overfitting",
                "Poor generalisation",
                "When a model performs well on training data but poorly "
                "on unseen data."
            ),
            (
                "SQL JOIN",
                "Combine related tables",
                "A JOIN combines rows from two or more tables using "
                "a related column."
            ),
            (
                "IoT",
                "Connected physical devices",
                "Devices with sensors and connectivity that collect or "
                "exchange data."
            ),
            (
                "ReLU",
                "Activation function",
                "ReLU(x) = max(0, x). It introduces non-linearity."
            ),
            (
                "Primary key",
                "Unique row identifier",
                "A primary key uniquely identifies each table record."
            )
        ]

        index = st.session_state["flash_index"] % len(cards)
        front, hint, answer = cards[index]

        st.markdown(
            f"""
            <div class="card" style="text-align:center;padding:45px 20px">
                <p style="color:#6b5bdb">FLASHCARD {index+1} / {len(cards)}</p>
                <h1>{front}</h1>
                <p>{hint}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.session_state["show_flash_answer"]:
            st.success(answer)

        b1, b2, b3 = st.columns(3)

        with b1:
            if st.button("← Previous", use_container_width=True):
                st.session_state["flash_index"] -= 1
                st.session_state["show_flash_answer"] = False
                st.rerun()

        with b2:
            if st.button("👀 Reveal answer", use_container_width=True):
                st.session_state["show_flash_answer"] = (
                    not st.session_state["show_flash_answer"]
                )
                st.rerun()

        with b3:
            if st.button("Next →", use_container_width=True):
                st.session_state["flash_index"] += 1
                st.session_state["show_flash_answer"] = False
                st.rerun()


# ------------------------- ASSIGNMENTS -------------------------

elif page == "🗓️ Assignments":

    st.markdown("""
    <div class="hero">
        <h1>Deadlines, under control. 🗓️</h1>
        <p>Organise your assignments, prioritise tasks and track completion.</p>
    </div>
    """, unsafe_allow_html=True)

    tasks = get_tasks()

    total = len(tasks)
    done = int(tasks["completed"].sum()) if total else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total tasks", total)
    c2.metric("Pending", total - done)
    c3.metric("Completed", done)

    st.progress(
        done / total if total else 0,
        text=f"Completion: {done/total:.0%}" if total else "Completion: 0%"
    )

    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Assignment name")
        subject = st.text_input("Subject")
        deadline = st.date_input(
            "Deadline",
            value=date.today() + timedelta(days=3)
        )
        priority = st.selectbox("Priority", ["High", "Medium", "Low"])

        submit = st.form_submit_button(
            "➕ Add assignment",
            type="primary"
        )

    if submit:
        if title.strip() and subject.strip():
            add_task(title.strip(), subject.strip(), deadline, priority)
            st.success("Assignment added!")
            st.rerun()
        else:
            st.warning("Please enter the task name and subject.")

    st.markdown("### 📋 Your tasks")

    filter_choice = st.selectbox(
        "Show",
        ["All", "Pending", "Completed"]
    )

    tasks = get_tasks()

    if filter_choice == "Pending":
        tasks = tasks[tasks["completed"] == 0]
    elif filter_choice == "Completed":
        tasks = tasks[tasks["completed"] == 1]

    if tasks.empty:
        st.info("No tasks in this view.")

    for _, task in tasks.iterrows():
        with st.container(border=True):
            left, right = st.columns([4, 1])

            with left:
                st.markdown(f"**{task['title']}**")
                st.caption(
                    f"{task['subject']} · Due {task['deadline']} · "
                    f"Priority: {task['priority']}"
                )

                due = date.fromisoformat(task["deadline"])

                if task["completed"]:
                    st.success("Completed")
                elif due < date.today():
                    st.error("Overdue")
                elif due == date.today():
                    st.warning("Due today")
                else:
                    st.info("Pending")

            with right:
                checked = st.checkbox(
                    "Completed",
                    value=bool(task["completed"]),
                    key=f"done_{task['id']}"
                )

                if checked != bool(task["completed"]):
                    with connect() as con:
                        con.execute(
                            "UPDATE tasks SET completed=? WHERE id=?",
                            (int(checked), int(task["id"]))
                        )
                    st.rerun()

                if st.button("Delete", key=f"delete_{task['id']}"):
                    with connect() as con:
                        con.execute(
                            "DELETE FROM tasks WHERE id=?",
                            (int(task["id"]),)
                        )
                    st.rerun()

    all_tasks = get_tasks()

    if not all_tasks.empty:
        st.download_button(
            "⬇️ Download task report",
            all_tasks.to_csv(index=False),
            "edumind_tasks.csv",
            "text/csv"
        )


# ------------------------- MY PROGRESS -------------------------

elif page == "📈 My Progress":

    st.markdown("""
    <div class="hero">
        <h1>Your progress, made visible. 📈</h1>
        <p>Review your learning activity, quiz results and task completion.</p>
    </div>
    """, unsafe_allow_html=True)

    tasks = get_tasks()
    sessions = get_sessions()
    quizzes = get_quiz_results()

    total = len(tasks)
    done = int(tasks["completed"].sum()) if total else 0

    average = (
        round((quizzes["score"] / quizzes["total"] * 100).mean())
        if not quizzes.empty else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Study sessions", len(sessions))
    c2.metric("Quiz attempts", len(quizzes))
    c3.metric("Tasks completed", f"{done}/{total}" if total else "0")
    c4.metric("Quiz average", f"{average}%" if not quizzes.empty else "—")

    st.markdown("### 📊 Quiz performance")

    if quizzes.empty:
        st.info("Complete a quiz to see your progress.")
    else:
        chart = quizzes.copy()
        chart["percentage"] = (
            chart["score"] / chart["total"] * 100
        ).round(1)

        st.line_chart(chart["percentage"])
        st.dataframe(chart, hide_index=True, use_container_width=True)

        st.download_button(
            "Download quiz history",
            quizzes.to_csv(index=False),
            "quiz_history.csv",
            "text/csv"
        )

    st.markdown("### ⏱️ Study activity")

    if sessions.empty:
        st.info("Log a study session in Student Toolkit.")
    else:
        grouped = sessions.groupby("subject")["minutes"].sum()
        st.bar_chart(grouped)

    st.markdown("### 🗓️ Assignment completion")
    st.progress(
        done / total if total else 0,
        text=f"{done}/{total} completed" if total else "No assignments yet"
    )


# ------------------------- STUDENT TOOLKIT -------------------------

elif page == "🛠️ Student Toolkit":

    st.markdown("""
    <div class="hero">
        <h1>Your everyday study tools. 🛠️</h1>
        <p>Log study sessions, calculate marks and plan your next study days.</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "⏱️ Study Log",
        "📊 Marks Calculator",
        "🗓️ Study Planner"
    ])

    with tab1:
        with st.form("study_log", clear_on_submit=True):
            subject = st.text_input(
                "Subject",
                value=st.session_state["focus_subject"]
            )
            minutes = st.number_input(
                "Focused minutes",
                min_value=5,
                max_value=600,
                value=25,
                step=5
            )
            study_date = st.date_input("Study date", value=date.today())

            save = st.form_submit_button(
                "Save study session",
                type="primary"
            )

        if save:
            if subject.strip():
                with connect() as con:
                    con.execute(
                        """INSERT INTO study_sessions(subject,minutes,study_date)
                           VALUES(?,?,?)""",
                        (subject.strip(), int(minutes), study_date.isoformat())
                    )
                st.success("Study session saved!")
                st.rerun()
            else:
                st.warning("Enter a subject.")

    with tab2:
        left, right = st.columns(2)

        with left:
            obtained = st.number_input(
                "Marks obtained", min_value=0.0, value=72.0
            )
            maximum = st.number_input(
                "Maximum marks", min_value=1.0, value=100.0
            )

            if obtained <= maximum:
                st.metric(
                    "Percentage",
                    f"{obtained / maximum * 100:.2f}%"
                )
            else:
                st.warning("Obtained marks cannot exceed maximum marks.")

        with right:
            target = st.slider("Target percentage", 1, 100, 80)
            required = maximum * target / 100

            st.metric("Marks needed for target", f"{required:.1f}")
            st.caption(
                f"Additional marks needed: {max(0, required-obtained):.1f}"
            )

    with tab3:
        subject = st.text_input(
            "Subject or exam",
            value=st.session_state["focus_subject"],
            key="planner_subject"
        )

        hours = st.slider("Hours available per day", 1, 8, 3)

        if st.button("Build my 3-day plan", type="primary"):
            plans = [
                ("Day 1 · Learn", "Understand concepts and examples."),
                ("Day 2 · Practise", "Solve questions and practical exercises."),
                ("Day 3 · Revise", "Recall important points and correct mistakes.")
            ]

            for title, description in plans:
                st.markdown(
                    f"""
                    <div class="card">
                        <h3>{title}</h3>
                        <b>{subject}</b><br>
                        {description}<br><br>
                        <span style="color:#6555d9">
                            Planned time: {hours} hour(s)
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ------------------------- FOOTER -------------------------

st.divider()

st.markdown("""
<div style="text-align:center;color:#8990a8;padding:12px">
    🎓 <b>EduMind AI</b> · Smart Student Workspace<br>
    College Project Prototype · Learn, practise and grow.
</div>
""", unsafe_allow_html=True)