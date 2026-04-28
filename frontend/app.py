

import streamlit as st
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from frontend.api_client import APIClient
from frontend.components.login import render_login
from frontend.components.query_interface import render_query_interface


st.set_page_config(
    page_title="ARGUS | The NL-SQL RAG Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "NL-SQL RAG Pipeline — Built by Dhanesh Vashisth"
    }
)

st.markdown("""
<style>
    /* Main background */
    .main {
        background-color: #0e1117;
    }

    /* Chat message styling */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 8px;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #1e2130;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #2d3250;
    }

    /* Code blocks */
    .stCode {
        border-radius: 8px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        transition: all 0.2s;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1d2e;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        font-size: 1rem;
        padding: 8px 20px;
    }

    /* Caption text */
    .stCaption {
        font-size: 0.8rem;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "api_client" not in st.session_state:
    st.session_state.api_client = APIClient()


api_client = st.session_state.api_client

if not st.session_state.logged_in:
    render_login(api_client)
else:
 
    if st.session_state.get("token"):
        api_client.set_token(st.session_state.token)

    render_query_interface(api_client)