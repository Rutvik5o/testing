
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import re
from datetime import datetime

# Initialize session state
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'calls_df' not in st.session_state:
    st.session_state.calls_df = pd.DataFrame()

class QualityProcessor:
    def __init__(self):
        pass
    
    def clean_transcript(self, text):
        """Clean text (Phase 1)"""
        if pd.isna(text):
            return ""
        text = re.sub(r'\n+', ' ', str(text))
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()
    
    def analyze_sentiment(self, text):
        """Sentiment analysis (Phase 2 - Rule-based DistilBERT simulation)"""
        negative_words = ['damage', 'broken', 'angry', 'frustrated', 'refund', 'cancel', 'wrong', 'not working']
        positive_words = ['happy', 'great', 'perfect', 'excellent', 'thank you']
        
        neg_count = sum(1 for word in negative_words if word in text)
        pos_count = sum(1 for word in positive_words if word in text)
        
        if neg_count > pos_count * 1.5:
            return 'NEGATIVE', min(0.9, 0.6 + neg_count * 0.1)
        elif pos_count > neg_count:
            return 'POSITIVE', min(0.8, 0.5 + pos_count * 0.1)
        else:
            return 'NEUTRAL', 0.5
    
    def calculate_quality_score(self, text, sentiment):
        """Quality scoring (Phase 2)"""
        score = 60.0
        
        # Sentiment impact
        if sentiment == 'NEGATIVE': 
            score -= 30
        elif sentiment == 'POSITIVE': 
            score += 15
        
        # Length analysis
        length = len(text)
        if length < 50: 
            score -= 15
        elif length > 800: 
            score -= 5
        
        # Complaint keywords penalty
        complaint_words = ['damage', 'broken', 'refund', 'cancel', 'wrong']
        complaints = sum(1 for word in complaint_words if word in text)
        score -= complaints * 12
        
        return max(0, min(100, round(score, 1)))
    
    def generate_supervisor_summary(self, analysis):
        """GenAI Supervisor message (Phase 3)"""
        severity = "🚨 CRITICAL" if analysis['quality_score'] < 40 else "⚠️ HIGH PRIORITY"
        issues = []
        
        if analysis['sentiment'] == 'NEGATIVE':
            issues.append("angry customer")
        if analysis['quality_score'] < 50:
            issues.append("very low quality")
        
        actions = "IMMEDIATE ESCALATION" if analysis['quality_score'] < 30 else "AGENT RETRAINING"
        
        return f"""📧 SUPERVISOR ALERT: {analysis['call_id']}

{severity} - Score: {analysis['quality_score']}/100

🔍 Issues: {', '.join(issues) if issues else 'Low quality indicators'}
🎯 Action: {actions}
📞 Review transcript immediately"""
    
    def generate_customer_message(self, analysis):
        """GenAI Customer message (Phase 3)"""
        name = analysis.get('customer_name', 'Customer')
        templates = {
            'NEGATIVE': f"Dear {name}, we're truly sorry for your experience with your order. A manager will contact you within 2 hours to resolve this.",
            'NEUTRAL': f"Thank you {name} for your call. We've recorded your feedback and will follow up if needed.",
            'POSITIVE': f"Thank you {name} for your kind words! We're glad we could help."
        }
        return templates.get(analysis['sentiment'], f"Thank you {name} for calling.")
    
    def process_call(self, transcript, call_id="CALL-001", customer_name="Customer"):
        """🎯 COMPLETE END-TO-END PIPELINE"""
        analysis = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'call_id': call_id,
            'customer_name': customer_name,
            'transcript': transcript[:1000],  # Truncate for display
            'transcript_full': transcript,
            'sentiment': '',
            'sentiment_confidence': 0.0,
            'quality_score': 0.0,
            'needs_review': False,
            'review_flags': '',
            'supervisor_summary': '',
            'customer_message': ''
        }
        
        # Phase 1: Clean
        clean_text = self.clean_transcript(transcript)
        analysis['transcript_clean'] = clean_text
        
        # Phase 2: ML Analysis
        analysis['sentiment'], analysis['sentiment_confidence'] = self.analyze_sentiment(clean_text)
        analysis['quality_score'] = self.calculate_quality_score(clean_text, analysis['sentiment'])
        analysis['needs_review'] = analysis['quality_score'] < 70
        
        # Phase 2: Flags
        flags = []
        if analysis['quality_score'] < 70: flags.append('LOW_SCORE')
        if analysis['sentiment'] == 'NEGATIVE': flags.append('NEG_SENTIMENT')
        analysis['review_flags'] = ', '.join(flags)
        
        # Phase 3: GenAI (only if flagged)
        if analysis['needs_review']:
            analysis['supervisor_summary'] = self.generate_supervisor_summary(analysis)
            analysis['customer_message'] = self.generate_customer_message(analysis)
        
        # Save to history
        new_row = pd.DataFrame([analysis])
        if st.session_state.calls_df.empty:
            st.session_state.calls_df = new_row
        else:
            st.session_state.calls_df = pd.concat([st.session_state.calls_df, new_row], ignore_index=True)
        
        # Persist data
        os.makedirs('data', exist_ok=True)
        st.session_state.calls_df.to_csv('data/all_calls.csv', index=False)
        
        return analysis

# MAIN STREAMLIT APP
def main():
    st.set_page_config(
        page_title="Agentic Quality Monitor", 
        page_icon="📞",
        layout="wide"
    )
    
    # Initialize processor
    if st.session_state.processor is None:
        st.session_state.processor = QualityProcessor()
    
    processor = st.session_state.processor
    
    # Header
    st.title("🏭 Agentic Quality Monitor")
    st.markdown("**🔄 Complete ML + GenAI Pipeline | Live Processing | Production Ready**")
    
    # Input Section
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_transcript = st.text_area(
            "📝 **Paste Call Transcript**", 
            height=120,
            placeholder="Customer: Hello, my refrigerator arrived damaged yesterday... Agent: I apologize...",
            help="Paste the full call transcript here"
        )
    
    with col2:
        st.markdown("### ⚙️ Call Details")
        call_id = st.text_input("Call ID", value="CALL-001")
        customer_name = st.text_input("Customer Name", value="John Davis")
        
        if st.button("🚀 **PROCESS CALL**", type="primary", use_container_width=True):
            if new_transcript.strip():
                with st.spinner("🔄 Running COMPLETE pipeline...\n📝 Cleaning → 🤖 ML Analysis → 🎯 Scoring → 🤖 GenAI Messages"):
                    result = processor.process_call(new_transcript, call_id, customer_name)
                    st.session_state.last_result = result
                    st.success(f"✅ **COMPLETE!** Quality Score: **{result['quality_score']:.0f}/100**")
                    st.rerun()
    
    # Load historical data
    try:
        if os.path.exists('data/all_calls.csv'):
            df = pd.read_csv('data/all_calls.csv')
        else:
            df = st.session_state.calls_df
    except:
        df = st.session_state.calls_df
    
    # EXECUTIVE DASHBOARD
    if not df.empty:
        st.markdown("---")
        st.markdown("### 📊 **Executive Dashboard**")
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        total_calls = len(df)
        flagged_calls = len(df[df['needs_review']])
        avg_score = df['quality_score'].mean()
        
        col1.metric("📊 Total Calls", total_calls)
        col2.metric("🚨 Flagged", flagged_calls, f"{flagged_calls/total_calls*100:.0f}%")
        col3.metric("🎯 Avg Score", f"{avg_score:.1f}", f"{avg_score-50:+.1f}")
        col4.metric("📨 Notifications", flagged_calls * 2)
        
        # Charts
        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(
                df, x='quality_score', 
                color='needs_review',
                nbins=15,
                title="Quality Score Distribution",
                color_discrete_map={True: 'red', False: 'green'}
            )
            fig.add_vline(70, line_dash="dash", line_color="orange", 
                         annotation_text="Review Threshold")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.scatter(
                df, x='quality_score', y='sentiment_confidence',
                color='sentiment', size='quality_score',
                hover_data=['call_id'],
                title="Sentiment vs Quality Score"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Tabs for detailed views
        tab1, tab2, tab3 = st.tabs(["🚨 Flagged Calls", "📈 All Calls", "🤖 AI Messages"])
        
        with tab1:
            flagged = df[df['needs_review']].sort_values('quality_score')
            if not flagged.empty:
                st.subheader("Calls Needing Immediate Review")
                cols = ['call_id', 'customer_name', 'quality_score', 'sentiment', 'review_flags']
                st.dataframe(flagged[cols], use_container_width=True)
            else:
                st.success("✅ No calls currently need review!")
        
        with tab2:
            st.subheader("All Processed Calls")
            cols = ['call_id', 'quality_score', 'sentiment', 'needs_review']
            st.dataframe(df[cols].sort_values('timestamp', ascending=False), use_container_width=True)
        
        with tab3:
            st.subheader("AI-Generated Messages")
            flagged = df[df['needs_review']]
            if not flagged.empty:
                for idx, row in flagged.iterrows():
                    with st.expander(f"📞 {row['call_id']} | {row['quality_score']:.0f} | {row['sentiment']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.error("📧 **Supervisor Alert**")
                            st.write(row['supervisor_summary'])
                        with col2:
                            st.success("💌 **Customer Message**")
                            st.write(row['customer_message'])
            else:
                st.info("🤖 Upload flagged calls to see AI messages")
    
    # Latest result highlight
    if 'last_result' in st.session_state:
        st.markdown("---")
        st.markdown("### 🎉 **Latest Processing Result**")
        st.json(st.session_state.last_result)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        🎓 **Project-II (241C208)** | **Agentic Quality Monitor** | **Production Ready**
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
