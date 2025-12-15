import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
from datetime import datetime

# -----------------------------
# Simple rule-based sentiment & scoring
# -----------------------------
NEGATIVE_WORDS = [
    "angry", "frustrated", "upset", "bad", "terrible", "awful",
    "broken", "damaged", "not working", "refund", "cancel", "delay",
    "issue", "problem", "complaint"
]
POSITIVE_WORDS = [
    "happy", "satisfied", "great", "good", "excellent", "awesome",
    "thanks", "thank you", "love", "amazing", "perfect"
]


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def analyze_sentiment(text: str):
    text = clean_text(text)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text)

    if neg_count > pos_count:
        label = "NEGATIVE"
    elif pos_count > neg_count:
        label = "POSITIVE"
    else:
        label = "NEUTRAL"

    # crude confidence
    total = neg_count + pos_count
    confidence = 0.5 if total == 0 else min(0.95, 0.5 + 0.1 * total)
    return label, round(confidence, 2)


def quality_score(text: str, sentiment: str) -> float:
    score = 70.0  # base

    # sentiment impact
    if sentiment == "NEGATIVE":
        score -= 25
    elif sentiment == "POSITIVE":
        score += 10

    # length impact
    L = len(text)
    if L < 60:
        score -= 10
    elif L > 800:
        score -= 5

    # negative keyword penalty
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in text.lower())
    score -= 5 * neg_hits

    return max(0, min(100, round(score, 1)))


def short_supervisor_summary(call_id, sent, score, text):
    severity = "🚨 Critical" if score < 40 else "⚠️ Needs Attention" if score < 70 else "✅ OK"
    main_issue = "Customer sounds upset" if sent == "NEGATIVE" else "Customer is generally fine"
    action = "Review call and consider escalation." if score < 40 else \
             "Review call for coaching points." if score < 70 else \
             "No immediate action required."
    return f"{severity} | {call_id}\n• Sentiment: {sent}\n• Score: {score}/100\n• Notes: {main_issue}\n• Action: {action}"


def short_customer_message(name, sent):
    name = name or "Customer"
    if sent == "NEGATIVE":
        return (
            f"Dear {name}, we are sorry for the trouble you faced. "
            "Our team is reviewing your case and will reach out with a solution as soon as possible."
        )
    elif sent == "POSITIVE":
        return (
            f"Dear {name}, thank you for your kind feedback. "
            "We are glad to have you as our customer!"
        )
    else:
        return (
            f"Dear {name}, thank you for contacting us. "
            "We have noted your request and will make sure it is handled properly."
        )


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(
    page_title="Agentic Quality Monitor",
    page_icon="📞",
    layout="wide",
)

# Initialize history in session state
if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(
        columns=[
            "timestamp", "call_id", "customer_name", "channel",
            "sentiment", "sentiment_confidence", "quality_score",
            "needs_review", "review_reason", "transcript",
            "supervisor_summary", "customer_message"
        ]
    )

# Top banner
st.markdown(
    """
    <style>
    .main-title {
        background: linear-gradient(90deg, #4c6fff, #22c1c3);
        padding: 18px 25px;
        border-radius: 12px;
        color: white;
        font-size: 26px;
        font-weight: 700;
        margin-bottom: 10px;
    }
    .sub-title {
        color: #555;
        font-size: 14px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<div class='main-title'>📞 Agentic Quality Monitor for Call Center</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='sub-title'>Upload call audio or paste transcript → Auto sentiment, quality score, and AI-like summaries.</div>",
    unsafe_allow_html=True,
)

# -----------------------------
# Input section (left) + Info (right)
# -----------------------------
col_left, col_right = st.columns([1.3, 1])

with col_left:
    st.markdown("### 🎤 Input Call")

    channel = st.radio(
        "Input type",
        ["Text Transcript", "Audio (MP3/WAV/M4A)"],
        horizontal=True,
    )

    call_id = st.text_input("Call ID", value=f"CALL-{len(st.session_state.history) + 1:03d}")
    customer_name = st.text_input("Customer Name (optional)", value="", placeholder="e.g., John Davis")

    transcript_text = ""
    audio_bytes = None

    if channel == "Text Transcript":
        transcript_text = st.text_area(
            "Paste full call transcript",
            height=160,
            placeholder=(
                "Customer: Hello, my refrigerator arrived damaged yesterday and it is not cooling properly...\n"
                "Agent: I'm sorry to hear that, let me check your order..."
            ),
        )
    else:
        uploaded_audio = st.file_uploader(
            "Upload call recording (audio)",
            type=["mp3", "wav", "m4a"],
        )
        if uploaded_audio is not None:
            audio_bytes = uploaded_audio.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.info(
                "This demo does not run a heavy speech-to-text model on Streamlit Cloud.\n"
                "You can manually paste the transcript below if needed."
            )
            transcript_text = st.text_area(
                "Optional: Paste transcript for analysis",
                height=120,
            )

    run_button = st.button("🚀 Analyze Call", type="primary", use_container_width=True)

with col_right:
    st.markdown("### ℹ️ How this works")
    st.markdown(
        """
        - ✅ Rule-based sentiment & quality scoring (fast & free)
        - ✅ Flags low-quality or negative calls for review
        - ✅ Generates:
            - Supervisor summary
            - Customer follow-up / thank-you message
        - ✅ All results stored in session for charts and history
        """
    )
    st.markdown("---")
    st.markdown("### 🎯 Review Threshold")
    review_threshold = st.slider("Minimum acceptable quality score", 0, 100, 70)

# -----------------------------
# Process one call
# -----------------------------
if run_button:
    if not transcript_text.strip():
        st.error("Please provide a transcript (for audio, paste at least a short summary).")
    else:
        with st.spinner("Analyzing call..."):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean = clean_text(transcript_text)
            sent_label, sent_conf = analyze_sentiment(clean)
            score = quality_score(clean, sent_label)
            needs_review = score < review_threshold
            reason = []
            if needs_review:
                reason.append("LOW_SCORE")
            if sent_label == "NEGATIVE":
                reason.append("NEG_SENTIMENT")
            review_reason = ", ".join(reason) if reason else "OK"

            sup_sum = short_supervisor_summary(call_id, sent_label, score, clean)
            cust_msg = short_customer_message(customer_name, sent_label)

            new_row = pd.DataFrame(
                [
                    {
                        "timestamp": ts,
                        "call_id": call_id,
                        "customer_name": customer_name or "",
                        "channel": channel,
                        "sentiment": sent_label,
                        "sentiment_confidence": sent_conf,
                        "quality_score": score,
                        "needs_review": needs_review,
                        "review_reason": review_reason,
                        "transcript": transcript_text.strip(),
                        "supervisor_summary": sup_sum,
                        "customer_message": cust_msg,
                    }
                ]
            )
            st.session_state.history = pd.concat(
                [st.session_state.history, new_row], ignore_index=True
            )

        st.success(f"Analysis complete! Quality Score: {score}/100, Sentiment: {sent_label}")

# -----------------------------
# If we have history, show dashboard
# -----------------------------
history = st.session_state.history

st.markdown("---")
st.markdown("## 📊 Quality Monitoring Dashboard")

if history.empty:
    st.info("No calls analyzed yet. Upload audio or paste text and click 'Analyze Call'.")
else:
    # KPIs
    total_calls = len(history)
    flagged_calls = history["needs_review"].sum()
    avg_score = history["quality_score"].mean()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Calls", total_calls)
    k2.metric("Flagged Calls", int(flagged_calls), f"{flagged_calls / total_calls * 100:.0f}%")
    k3.metric("Avg Quality Score", f"{avg_score:.1f}")
    k4.metric("Review Threshold", review_threshold)

    # Charts
    c1, c2 = st.columns(2)

    with c1:
        fig1 = px.histogram(
            history,
            x="quality_score",
            nbins=10,
            color="needs_review",
            color_discrete_map={True: "#ff6b6b", False: "#4CAF50"},
            title="Quality Score Distribution",
        )
        fig1.add_vline(review_threshold, line_dash="dash", line_color="orange")
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        fig2 = px.scatter(
            history,
            x="quality_score",
            y="sentiment_confidence",
            color="sentiment",
            hover_data=["call_id"],
            title="Sentiment Confidence vs Quality Score",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Tabs for details
    tab1, tab2, tab3 = st.tabs(["🚨 Flagged Calls", "📜 All Calls", "🤖 AI Messages"])

    with tab1:
        st.markdown("### 🚨 Calls Needing Review")
        fl = history[history["needs_review"]].copy()
        if fl.empty:
            st.success("No calls currently need review. 👍")
        else:
            cols = ["timestamp", "call_id", "customer_name", "quality_score", "sentiment", "review_reason"]
            st.dataframe(fl[cols].sort_values("timestamp", ascending=False), use_container_width=True)

    with tab2:
        st.markdown("### 📜 All Analyzed Calls")
        cols = ["timestamp", "call_id", "customer_name", "channel", "quality_score", "sentiment", "needs_review"]
        st.dataframe(history[cols].sort_values("timestamp", ascending=False), use_container_width=True)

    with tab3:
        st.markdown("### 🤖 Generated Messages")
        for _, row in history.sort_values("timestamp", ascending=False).iterrows():
            with st.expander(f"📞 {row['call_id']} | {row['sentiment']} | {row['quality_score']}/100"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Supervisor Summary**")
                    st.code(row["supervisor_summary"])
                with c2:
                    st.markdown("**Customer Message**")
                    st.code(row["customer_message"])

st.markdown("---")
st.caption("Project-II • Agentic Quality Monitor • Streamlit Demo")
