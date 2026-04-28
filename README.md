# 🧠 NL-SQL RAG Pipeline 

> A production-grade, plug-and-play Natural Language to SQL system which I **named it as ARGUS**.
> Ask questions in plain English. Get SQL-powered answers.
> Works with **any PostgreSQL database** in **any industry**.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1.19-orange)](https://langchain-ai.github.io/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red)](https://qdrant.tech)
[![Redis](https://img.shields.io/badge/Redis-Semantic_Cache-red)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-35%2B_passing-brightgreen)]()

---

## 📌 What Is This?

This system lets **non-technical users query any PostgreSQL database**
using plain English questions — no SQL knowledge required.

It was built for a gaming transaction platform but is designed to be
**adapted to any industry** — hospitals, banks, e-commerce, HR systems,
inventory management, and more.

**How it works in one line:**
```
"show me pending transactions" → SQL → "There are 47 pending transactions totaling $12,456"
```

**With automatic security:**
```
Agent asks:      "show all transactions"
System executes: SELECT ... FROM transactions WHERE agent_id = 4
                                                ↑ automatically added
```

---

## 🏭 Use This In Your Own Industry

This is a **plug-and-play system**. You can adapt it to any database
by changing just **3 files**. Everything else (pipeline, cache, auth,
API, UI) stays exactly the same.

### 🏥 Example: Hospital Database

**Your existing tables:**
```sql
patients (id, name, age, blood_type, admitted_at)
doctors (id, name, department, specialization)
appointments (id, patient_id, doctor_id, date, status)
prescriptions (id, patient_id, doctor_id, medicine, dosage)
```

**Step 1 — Replace `app/db/schema.sql`**

Write your hospital schema:
```sql
CREATE TYPE appointment_status AS ENUM ('scheduled', 'completed', 'cancelled');
CREATE TYPE user_role AS ENUM ('admin', 'supervisor', 'agent');
-- keep user_role enum — it powers the auth system

CREATE TABLE patients (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    age          INTEGER,
    blood_type   VARCHAR(5),
    admitted_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE doctors (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    department     VARCHAR(100),
    specialization VARCHAR(100)
);

CREATE TABLE appointments (
    id         SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    doctor_id  INTEGER REFERENCES doctors(id),
    date       TIMESTAMPTZ,
    status     appointment_status DEFAULT 'scheduled'
);
-- Keep the users table from original schema.sql for auth
```

**Step 2 — Replace `app/vector_store/schema_docs.py`**

Describe your tables in plain English (this is what the AI reads):
```python
SCHEMA_DOCUMENTS = [
    {
        "doc_id": "patients_table",
        "table_name": "patients",
        "content": """
Table: patients
Purpose: Stores all patient records in the hospital.

Columns:
- id: Unique patient identifier
- name: Patient full name
- age: Patient age in years
- blood_type: Blood type (A+, B+, O+, AB+, etc.)
- admitted_at: When patient was admitted

Common questions this table answers:
- How many patients were admitted this week?
- Show patients with blood type O+
- List all patients over 60 years old
- How many patients are currently admitted?
""",
        "sql_reference": {
            "table": "patients",
            "key_columns": ["id", "name", "age", "blood_type", "admitted_at"]
        }
    },
    {
        "doc_id": "appointments_table",
        "table_name": "appointments",
        "content": """
Table: appointments
Purpose: Tracks all doctor-patient appointments.

Columns:
- id: Unique appointment identifier
- patient_id: References patients.id
- doctor_id: References doctors.id
- date: Appointment date and time
- status: scheduled, completed, or cancelled

Common questions this table answers:
- How many appointments are scheduled today?
- Show cancelled appointments this week
- Which doctor has the most appointments?
- Show all upcoming appointments
""",
        "sql_reference": {
            "table": "appointments",
            "key_columns": ["id", "patient_id", "doctor_id", "date", "status"],
            "status_values": ["scheduled", "completed", "cancelled"]
        }
    }
    # Add one entry per table in your database
]
```

**Step 3 — Replace `app/db/seed.py`**

Seed your hospital test data instead of gaming transactions.
The `users` table (admin/supervisor/agent) stays the same
for the auth system. Add your domain data below it.

**That's it. 3 files changed. Everything else works.**

---

### 🏦 Example: Banking System

| Your Table | Replace In |
|-----------|-----------|
| `accounts`, `loans`, `transfers` | `schema.sql` |
| Descriptions of accounts/loans | `schema_docs.py` |
| Bank branch test data | `seed.py` |

**Sample schema doc for banking:**
```python
{
    "doc_id": "accounts_table",
    "table_name": "accounts",
    "content": """
Table: accounts
Purpose: Customer bank accounts

Columns:
- id: Account number
- customer_name: Account holder name
- balance: Current balance in dollars
- account_type: savings, checking, or fixed_deposit
- status: active, frozen, or closed
- opened_at: When account was opened

Common questions:
- Show all accounts with balance above $10,000
- How many accounts were opened this month?
- Show frozen accounts
- What is the total balance across all accounts?
""",
    "sql_reference": {
        "table": "accounts",
        "key_columns": ["id", "customer_name", "balance",
                       "account_type", "status", "opened_at"]
    }
}
```

### 🛒 Example: E-Commerce System

| Your Table | Replace In |
|-----------|-----------|
| `products`, `orders`, `customers` | `schema.sql` |
| Descriptions of products/orders | `schema_docs.py` |
| Sample products and orders | `seed.py` |

### 🏭 Any Industry Checklist

When adapting to a new database, answer these questions:

- [ ] What are my table names?
- [ ] What does each column store?
- [ ] What questions will users ask most often?
- [ ] What roles should have restricted access?
- [ ] What column enforces that restriction? (like `agent_id`, `doctor_id`)

Fill these answers into `schema_docs.py` and `schema.sql`.
The AI learns your database from these descriptions.

---

## 🔐 Adapting the RBAC System

The current system has 3 roles: **admin → supervisor → agent**

This maps to almost every organizational hierarchy:
- Hospital: **Admin → Department Head → Doctor**
- Bank: **Admin → Branch Manager → Teller**
- E-commerce: **Admin → Regional Manager → Store Agent**

**To rename roles** — edit `app/auth/models.py`:
```python
class UserRole(str, Enum):
    ADMIN      = "admin"       # rename to "hospital_admin"
    SUPERVISOR = "supervisor"  # rename to "department_head"
    AGENT      = "agent"       # rename to "doctor"
```

**To change what data each role sees** — edit `get_rbac_scope()` in `app/auth/models.py`:
```python
# Hospital example: doctors only see their own patients
elif token_data.role == UserRole.AGENT:  # "doctor"
    return RBACScope(
        filter_column="doctor_id",   # ← your column name
        filter_value=token_data.user_id,
        description=f"Doctor {token_data.username}: own patients only"
    )
```

**To change what column scopes the data** — just update `filter_column`
to whatever column in your table stores the owner's ID.

---

## 🚀 Installation — Step by Step

Follow every step exactly. Each command is explained.

### Prerequisites

Before starting, install these on your machine:

| Tool | Download | Why needed |
|------|---------|-----------|
| Python 3.11+ | [python.org](https://python.org) | Runs the application |
| Docker Desktop | [docker.com](https://docker.com/products/docker-desktop) | Runs PostgreSQL, Qdrant, Redis |
| Git | [git-scm.com](https://git-scm.com) | Clone the repository |
| OpenAI API Key | [platform.openai.com](https://platform.openai.com) | Powers SQL generation |

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/dhaneshvashisth/NL-SQL-RAG-Pipeline.git
cd NL-SQL-RAG-Pipeline
```

**What this does:** Downloads the project to your computer.

---

### Step 2 — Create Your Environment File

```bash
# Copy the template
cp .env.example .env
```

Now open `.env` in any text editor and fill in:

```env
# PostgreSQL — leave as is, matches docker-compose
POSTGRES_USER=nlsql_user
POSTGRES_PASSWORD=nlsql_pass_2024
POSTGRES_DB=nlsql_db
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433

# Qdrant — leave as is
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=schema_embeddings

# Redis — leave as is
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_TTL_SECONDS=3600

# OpenAI — REPLACE WITH YOUR KEY
OPENAI_API_KEY=sk-your-actual-key-here

# JWT — REPLACE WITH ANY LONG RANDOM STRING
JWT_SECRET_KEY=make-this-very-long-and-random-minimum-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60

# App
APP_ENV=development
LOG_LEVEL=INFO
```

**What this does:** Configures all connection details and secrets.
**Important:** Never commit this file to Git. It's in `.gitignore`.

---

### Step 3 — Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# You should see (venv) in your terminal now
```

**What this does:** Creates an isolated Python environment so
this project's packages don't conflict with other projects.

---

### Step 4 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

**What this does:** Installs all packages — FastAPI, LangGraph,
Qdrant client, Redis, asyncpg, Streamlit, and more.

This takes 2-5 minutes on first run.

---

### Step 5 — Start Infrastructure with Docker

```bash
# Start PostgreSQL, Qdrant, and Redis
docker-compose up -d postgres qdrant redis
```

**What this does:** Starts 3 services in Docker containers:
- PostgreSQL on port 5433 (your transaction database)
- Qdrant on port 6333 (vector store for schema embeddings)
- Redis on port 6379 (semantic cache)

**Verify they started:**
```bash
docker-compose ps
```

All 3 should show `running (healthy)`. Wait 20 seconds if not.

---

### Step 6 — Create Database Tables and Sample Data

```bash
python -m app.db.seed
```

**What this does:** Creates all database tables and inserts:
- 1 Admin user
- 3 Supervisors
- 9 Agents (3 per supervisor)
- 5 gaming platforms
- ~479 realistic transactions

**Expected output:**
```
INFO | DATABASE SEEDING COMPLETE
INFO | Admin    : 1  | login: admin_dv / Admin@1234
INFO | Supervisors: 3 | login: supervisor_virat / Super@1234
INFO | Agents   : 9  | login: agent_dhoni / Agent@1234
INFO | Transactions: 479
```

---

### Step 7 — Index Schema into Qdrant

```bash
python -m app.vector_store.indexer
```

**What this does:** Converts your database schema descriptions
into vectors and stores them in Qdrant. This is the RAG step —
it's what allows the AI to find relevant tables for each question.

**Expected output:**
```
INFO | Schema indexing complete | 5 documents stored in Qdrant
```

**Verify in browser:** Open `http://localhost:6333/dashboard`
→ Collections → `schema_embeddings` → should show 5 points.

---

### Step 8 — Start the API

```bash
uvicorn app.api.main:app --reload --port 8000
```

**What this does:** Starts the FastAPI backend that handles:
- User authentication (login → JWT token)
- Natural language queries (question → SQL → answer)
- Query history and audit logging

**Verify:** Open `http://localhost:8000/health` in browser.
Should return `{"status": "healthy"}`.

**API Documentation:** Open `http://localhost:8000/docs`
to see all endpoints with interactive testing.

---

### Step 9 — Start the Frontend

Open a **new terminal** (keep API running in first terminal):

```bash
# Activate venv in new terminal
venv\Scripts\activate

# Start Streamlit
streamlit run frontend/app.py
```

**What this does:** Starts the Streamlit web interface at
`http://localhost:8501`

The browser opens automatically.

---

### Step 10 — Test the System

Open `http://localhost:8501` and:

1. **Login as Admin:** `admin_dv` / `Admin@1234`
2. **Ask:** *"show total deposits by platform this month"*
3. **See:** Generated SQL + formatted answer + timing metrics
4. **Ask same question again** → notice `⚡ Cache Hit` (much faster)
5. **Login as Agent:** `agent_dhoni` / `Agent@1234`
6. **Ask same question** → notice SQL has `AND agent_id = X` appended

---

## ⚡ One-Command Setup (Recommended)

Clone the repo and run everything with a single command.
No separate terminals. No manual steps.

### Prerequisites
- Docker Desktop running
- OpenAI API Key

### Steps

**1. Clone and enter the project**
```bash
git clone https://github.com/YOUR_USERNAME/NL-SQL-RAG-Pipeline.git
cd NL-SQL-RAG-Pipeline
```

**2. Create your `.env` file**
```bash
cp .env.example .env
# Open .env and add your OPENAI_API_KEY and JWT_SECRET_KEY
```

**3. Start everything**
```bash
docker-compose up -d --build
```

This single command:
- Builds the FastAPI and Streamlit images
- Starts PostgreSQL, Qdrant, Redis, API, and Frontend
- Waits for each service to be healthy before starting the next

**4. Initialize database and vector store (first time only)**
```bash
docker exec nl_sql_api python scripts/start.py
```

**5. Open the app**

| Service | URL |
|---------|-----|
| 🖥️ Frontend | http://localhost:8501 |
| 📡 API Docs | http://localhost:8000/docs |
| 🔍 Qdrant UI | http://localhost:6333/dashboard |

**Login with:** `admin_dv` / `Admin@1234`

**Stop everything:**
```bash
docker-compose down
```

**Full reset (deletes all data):**
```bash
docker-compose down -v
```

---

## 🐳 Full Docker Deployment (Optional)

Run everything including API and Streamlit in Docker:

```bash
# Build all images
docker-compose build --no-cache

# Start all 5 services
docker-compose up -d

# Run initialization (first time only)
docker exec nl_sql_api python scripts/start.py

# Check all services
docker-compose ps
```

**View logs:**
```bash
docker-compose logs -f api          # API logs
docker-compose logs -f streamlit    # Frontend logs
docker-compose logs -f postgres     # Database logs
```

**Stop everything:**
```bash
docker-compose down
```

**Full reset (deletes all data):**
```bash
docker-compose down -v
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific categories
pytest tests/test_security.py -v    # SQL injection + RBAC + cache security
pytest tests/test_pipeline.py -v    # Full pipeline integration tests
pytest tests/test_auth.py -v        # JWT + login tests
pytest tests/test_cache.py -v       # Semantic cache tests
```

**Expected:** 35+ tests passing.

**What the tests verify:**
- SQL injection attempts are blocked (`DROP TABLE` etc.)
- Admin cache results never leak to agents
- Agent SQL always has `AND agent_id = X` appended
- Invalid tokens are rejected
- Pipeline completes end-to-end for all 3 roles

---

## 💬 Example Questions by Role

### Admin (Full Access)
```
"show total deposits by platform this month"
"which agent has the most transactions this week"
"compare completed vs pending transactions"
"show daily transaction summary for last 7 days"
"which platform has the highest failure rate"
"show all transactions above $1000 today"
```

### Supervisor (Team Access Only)
```
"show my team's total transactions"
"which of my agents has the most deposits"
"compare my agents performance this week"
"show pending transactions for my team"
"total withdrawal amount for my team this month"
```

### Agent (Own Data Only)
```
"show all my transactions"
"what is my total deposit amount"
"show my pending transactions"
"how many transactions did I process this week"
"show my transactions for 4RABET platform"
```

---

## 📁 Project Structure

```
NL-SQL-RAG-Pipeline/
│
├── app/                          # Core application
│   ├── api/
│   │   ├── main.py               # FastAPI app + startup
│   │   ├── dependencies.py       # Shared FastAPI dependencies
│   │   └── routes/
│   │       ├── auth.py           # POST /auth/login, GET /auth/me
│   │       └── query.py          # POST /query/, GET /query/history
│   │
│   ├── auth/
│   │   ├── models.py             # UserRole enum, TokenData, RBACScope
│   │   ├── jwt_handler.py        # create_access_token, decode_access_token
│   │   └── rbac.py               # get_current_user, require_admin
│   │
│   ├── cache/
│   │   └── redis_cache.py        # SemanticCache with cosine similarity
│   │
│   ├── db/
│   │   ├── connection.py         # asyncpg pool (create, get, close)
│   │   ├── schema.sql            # ⭐ REPLACE FOR YOUR DATABASE
│   │   └── seed.py               # ⭐ REPLACE FOR YOUR DATA
│   │
│   ├── graph/                    # LangGraph pipeline
│   │   ├── state.py              # GraphState TypedDict
│   │   ├── pipeline.py           # Graph assembly + run_pipeline()
│   │   └── nodes/
│   │       ├── schema_retrieval.py   # Node 1: Qdrant search
│   │       ├── sql_generation.py     # Node 2: GPT-4o-mini
│   │       ├── sql_validation.py     # Node 3: Security + RBAC
│   │       ├── sql_execution.py      # Node 4: asyncpg
│   │       └── response_formatter.py # Node 5: GPT-4o-mini
│   │
│   ├── vector_store/
│   │   ├── client.py             # Qdrant connection
│   │   ├── embedder.py           # text-embedding-3-small
│   │   ├── indexer.py            # index + retrieve schemas
│   │   └── schema_docs.py        # ⭐ REPLACE FOR YOUR SCHEMA
│   │
│   └── utils/
│       ├── config.py             # All env vars in one place
│       ├── logger.py             # Structured logging
│       └── prompt_templates.py   # All LLM prompts
│
├── frontend/
│   ├── app.py                    # Streamlit entry point
│   ├── api_client.py             # HTTP client for FastAPI
│   └── components/
│       ├── login.py              # Login page
│       └── query_interface.py    # Chat + history + analytics
│
├── tests/
│   ├── conftest.py               # Shared fixtures (tokens, client)
│   ├── test_auth.py              # 15+ auth tests
│   ├── test_security.py          # 12+ security tests
│   ├── test_cache.py             # 8+ cache tests
│   └── test_pipeline.py          # 7+ integration tests
│
├── scripts/
│   └── start.py                  # One-command initialization
│
├── Dockerfile                    # Container definition
├── docker-compose.yml            # Full stack orchestration
├── pg_hba.conf                   # PostgreSQL auth config
├── pytest.ini                    # Test configuration
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── README.md
```

**⭐ = Files to replace when adapting to your own database**

---

## 🔑 Key Engineering Decisions

### Why LangGraph over a simple LangChain chain?
LangGraph provides a **stateful graph with conditional edges**.
When SQL validation fails, the graph loops back to SQL generation
with the error message — enabling self-correction. A linear chain
cannot express this branching retry logic cleanly.

### Why Qdrant over FAISS or Pinecone?
Qdrant is **self-hosted** (no cloud costs in development),
**persistent** (survives restarts), and has a REST API + dashboard.
FAISS is an in-memory library — data is lost on restart.
Pinecone is cloud-only with usage costs.

### Why semantic cache over exact-match cache?
*"show pending transactions"* and *"list incomplete payments"*
mean the same thing. Exact-match cache treats them as different
queries. Semantic cache uses cosine similarity (threshold: 0.92)
to recognize equivalent questions — **saving one full LLM call
(~$0.001) and ~3 seconds per repeated similar query**.

### Why RBAC at SQL level, not UI level?
Hiding UI buttons is **trivially bypassed** with direct API calls
(curl, Postman, Python requests). Appending WHERE clauses
programmatically in the validation node makes access control
**impossible to bypass** — even through prompt injection or
direct API calls with a valid token.

### Why asyncpg over psycopg2?
FastAPI is async. asyncpg is a **native async PostgreSQL driver**
that releases the event loop during I/O. psycopg2 blocks the
entire thread while waiting for PostgreSQL — with 50 concurrent
users, psycopg2 would serialize all DB queries. asyncpg handles
them concurrently.

### Why cache keys include role + user_id?
*"show all transactions"* returns different data for admin
(all 479) vs agent (their 55). Without role-scoped cache keys,
admin's cached result would be returned to agents — a critical
data leakage vulnerability we caught and fixed in testing.

---

## 🏗️ Pipeline Flow

```
POST /query/ {"question": "show pending transactions"}
    ↓
[JWT Verification] → extract role, user_id
    ↓
[Embed Question] text-embedding-3-small → 1536-dim vector
    ↓
[Redis Semantic Cache] cosine_similarity > 0.92?
    ├── HIT  → return cached answer (< 500ms)
    └── MISS → continue pipeline
    ↓
[Node 1 — Schema Retrieval]
    → search Qdrant with question vector
    → retrieve top-3 most similar schema docs
    ↓
[Node 2 — SQL Generation]
    → GPT-4o-mini + schema context + few-shot examples
    → temperature=0, SELECT only
    ↓
[Node 3 — Validation + RBAC]
    → reject forbidden keywords (DROP, DELETE, INSERT...)
    → verify SELECT statement
    → inject WHERE clause based on role
    → FAIL? → back to Node 2 with error (max 3 retries)
    ↓
[Node 4 — SQL Execution]
    → asyncpg connection pool
    → non-blocking PostgreSQL query
    ↓
[Node 5 — Response Formatting]
    → GPT-4o-mini formats rows into natural language
    ↓
[Store in Cache] + [Log to query_logs]
    ↓
QueryResponse {answer, sql, row_count, cache_hit, time_ms}
```

---

## 👤 Demo Credentials

| Role | Username | Password | Sees |
|------|----------|----------|------|
| Admin | `admin_dv` | `Admin@1234` | All 479 transactions |
| Supervisor | `supervisor_virat` | `Super@1234` | Virat's team (3 agents) |
| Supervisor | `supervisor_rohit` | `Super@1234` | Rohit's team (3 agents) |
| Supervisor | `supervisor_hardik` | `Super@1234` | Hardik's team (3 agents) |
| Agent | `agent_dhoni` | `Agent@1234` | Dhoni's transactions only |
| Agent | `agent_sachin` | `Agent@1234` | Sachin's transactions only |
| Agent | `agent_sehwag` | `Agent@1234` | Sehwag's transactions only |

---

## 🌐 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Streamlit UI | http://localhost:8501 | Main user interface |
| FastAPI | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Interactive API documentation |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector store UI |

---

## 🐛 Troubleshooting

### "Connection refused" on port 5433
```bash
# Check if Docker containers are running
docker-compose ps

# If postgres shows unhealthy, check logs
docker-compose logs postgres
```

### "OPENAI_API_KEY not set"
```bash
# Verify your .env file has the key
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('OPENAI_API_KEY'))"
```

### "Collection not found" in Qdrant
```bash
# Re-run the indexer
python -m app.vector_store.indexer
```

### Streamlit shows "Cannot connect to API"
```bash
# Make sure FastAPI is running in another terminal
uvicorn app.api.main:app --reload --port 8000
```

### Tests failing with import errors
```bash
# Make sure venv is activated
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 👨‍💻 Author

**Dhanesh Vashisth** — AI Backend Engineer

Specialized in agentic AI systems, RAG pipelines,
and production-grade Python backend development.

---

## 📄 License

MIT License — free to use, adapt, and build upon.
If you adapt this for your industry, a ⭐ on the repo is appreciated!