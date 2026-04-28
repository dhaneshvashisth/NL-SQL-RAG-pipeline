
import streamlit as st


def render_login(api_client) -> bool:
    """
    Renders the login page.
    Returns True if login was successful (triggers app rerun).

    WHY RETURN BOOL?
    Main app.py checks this to know whether to show
    the query interface or stay on login page.
    """

    st.markdown("""
    <div style='text-align: center; padding: 2rem 0'>
        <h1 style='color: #667eea; font-size: 2.5rem'>
            ARGUS | NL-SQL RAG Agent
        </h1>
        <p style='color: #666; font-size: 1.1rem'>
            Natural Language → PostgreSQL | Role-Based Access Control
        </p>
        <p style='color: #888; font-size: 0.9rem'>
            Built with LangGraph · Qdrant · Redis · GPT-4o-mini · FastAPI
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    with st.expander("⚙️ System Architecture", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            **🔍 RAG Pipeline**
            - Qdrant vector store
            - OpenAI embeddings
            - Schema retrieval
            """)
        with col2:
            st.markdown("""
            **🤖 LangGraph**
            - 5-node stateful graph
            - Conditional retry loop
            - Self-correcting SQL
            """)
        with col3:
            st.markdown("""
            **🔐 Security**
            - OAuth2 + JWT
            - Role-based scoping
            - Query audit logs
            """)

    st.divider()

    st.subheader("🔑 Login")

    with st.expander("👤 Demo Credentials", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
            **Admin** (Full Access)
                        
            Username: admin_dv
                        
            Password: Admin@1234
            """)
        with c2:
            st.markdown("""
            **Supervisor** (Team Access)
                        
            Username: supervisor_virat
                        
            Password: Super@1234
            """)
        with c3:
            st.markdown("""
            **Agent** (Own Data Only)
                        
            Username: agent_dhoni
                        
            Password: Agent@1234
            """)

    col_left, col_right = st.columns([1, 1])

    with col_left:
        username = st.text_input(
            "Username",
            placeholder="e.g. admin_dv",
            key="login_username"
        )

    with col_right:
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
            key="login_password"
        )

    login_clicked = st.button(
        "🚀 Login",
        type="primary",
        use_container_width=True
    )

    if login_clicked:
        if not username or not password:
            st.error("Please enter both username and password")
            return False

        with st.spinner("Authenticating..."):
            result = api_client.login(username, password)

        if result["success"]:
            data = result["data"]
            st.session_state.token       = data["access_token"]
            st.session_state.username    = data["username"]
            st.session_state.role        = data["role"]
            st.session_state.user_id     = data["user_id"]
            st.session_state.logged_in   = True
            st.session_state.chat_history = []

            st.success(f"Welcome, {data['username']}! Role: {data['role'].upper()}")
            st.rerun()
            return True
        else:
            st.error(f"Login failed: {result['error']}")
            return False

    return False