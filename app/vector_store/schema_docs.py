SCHEMA_DOCUMENTS = [
            {
                "doc_id": "users_table",
                "table_name": "users",
                "content": """
                    Table: users
                    Purpose: Stores all system users across three roles — admin, supervisor, and agent.
                    The hierarchy is: Admin manages Supervisors, Supervisors manage Agents.

                    Columns:
                    - id (integer): Unique user identifier. Primary key.
                    - username (text): Login username. Examples: admin_dv, supervisor_virat, agent_dhoni
                    - email (text): User email address
                    - full_name (text): Display name. Examples: Dhanesh Vashisth, Virat Kohli, MS Dhoni
                    - role (enum): One of 'admin', 'supervisor', 'agent'
                    - parent_id (integer): References the manager's id.
                    - Admin has parent_id = NULL (no manager)
                    - Supervisor's parent_id = admin's id
                    - Agent's parent_id = their supervisor's id
                    - is_active (boolean): Whether account is active
                    - created_at (timestamp): When account was created

                    Relationships:
                    - users.parent_id → users.id (self-referencing hierarchy)
                    - users.id → transactions.agent_id (agents handle transactions)

                    Common queries answered by this table:
                    - How many agents does supervisor X have?
                    - List all supervisors under the admin
                    - Which agents are active/inactive?
                    - Who is agent dhoni's supervisor?
                    - Show me the team structure
                    - How many users are in each role?
                    """,
                "sql_reference": {
                    "table": "users",
                    "key_columns": ["id", "username", "full_name", "role", "parent_id", "is_active"],
                    "role_values": ["admin", "supervisor", "agent"]
                }
            },

            {
                "doc_id": "transactions_table",
                "table_name": "transactions",
                "content": """
                    Table: transactions
                    Purpose: Core business data. Every financial transaction processed by agents
                    from gaming platforms. This is the most queried table in the system.

                    Columns:
                    - id (integer): Unique transaction identifier
                    - reference_code (text): External transaction ID. Format: TXN-XXXX-XXXXXXXX
                    - agent_id (integer): Which agent processed this transaction → references users.id
                    - platform_id (integer): Which gaming platform sent this → references platforms.id
                    - customer_name (text): End customer's name (not a system user)
                    - customer_phone (text): Customer's phone number
                    - amount (decimal): Transaction amount in dollars. Can range from $1 to $5000
                    - transaction_type (enum): One of 'deposit', 'withdrawal', 'bonus', 'adjustment'
                    - deposit: customer adding money
                    - withdrawal: customer taking money out
                    - bonus: promotional credit
                    - adjustment: manual correction
                    - status (enum): One of 'pending', 'completed', 'failed', 'reversed'
                    - pending: not yet processed
                    - completed: successfully processed
                    - failed: processing failed
                    - reversed: transaction was reversed/refunded
                    - created_at (timestamp): When transaction was received
                    - processed_at (timestamp): When transaction was completed (NULL if pending)
                    - notes (text): Optional agent notes

                    Relationships:
                    - transactions.agent_id → users.id
                    - transactions.platform_id → platforms.id

                    Common queries answered by this table:
                    - Show me all pending transactions
                    - What is the total deposit amount today?
                    - How many transactions did agent dhoni process this week?
                    - Show failed transactions for platform 4RABET
                    - What is the average transaction amount?
                    - Compare deposits vs withdrawals this month
                    - Show transactions above $1000
                    - How many transactions are pending right now?
                    - What is agent sachin's total transaction volume?
                    - Show me all reversed transactions this month
                    - Daily transaction summary for the last 7 days
                    """,
                "sql_reference": {
                    "table": "transactions",
                    "key_columns": ["id", "reference_code", "agent_id", "platform_id",
                                "amount", "transaction_type", "status", "created_at", "processed_at"],
                    "transaction_types": ["deposit", "withdrawal", "bonus", "adjustment"],
                    "status_values": ["pending", "completed", "failed", "reversed"]
                }
            },

            {
                "doc_id": "platforms_table",
                "table_name": "platforms",
                "content": """
                    Table: platforms
                    Purpose: Gaming platforms that send transaction data into the system.
                    Each transaction comes from one platform.

                    Columns:
                    - id (integer): Unique platform identifier
                    - name (text): Platform display name. Values: 4RABET, 1xCASINO, BetNinja, MegaDice, PointsBet
                    - code (text): Short code. Values: 4BT, CAS, BNJ, MD, PB
                    - is_active (boolean): Whether platform is currently active
                    - created_at (timestamp): When platform was added

                    Relationships:
                    - platforms.id → transactions.platform_id

                    Common queries answered by this table (usually joined with transactions):
                    - Which platform has the most transactions?
                    - Compare revenue across all platforms
                    - Show total deposits by platform
                    - How many transactions came from 4RABET this week?
                    - Which platform has the highest failure rate?
                    - Show platform-wise breakdown of transaction types
                    - What is the average transaction amount per platform?
                    """,
                "sql_reference": {
                    "table": "platforms",
                    "key_columns": ["id", "name", "code", "is_active"],
                    "platform_names": ["4RABET", "1xCASINO", "BetNinja", "MegaDice", "PointsBet"],
                    "platform_codes": ["4BT", "CAS", "BNJ", "MD", "PB"]
                }
            },

            {
                "doc_id": "query_logs_table",
                "table_name": "query_logs",
                "content": """
                    Table: query_logs
                    Purpose: Audit trail for every natural language query submitted through
                    the pipeline. Used for security auditing, debugging, and analytics.

                    Columns:
                    - id (integer): Unique log entry identifier
                    - user_id (integer): Who asked the question → references users.id
                    - natural_language_query (text): The original question the user typed
                    - generated_sql (text): The SQL query the pipeline generated
                    - was_cache_hit (boolean): Was this answered from Redis cache?
                    - execution_time_ms (integer): How long the full pipeline took in milliseconds
                    - row_count (integer): How many rows were returned
                    - error_message (text): NULL if successful, error details if failed
                    - created_at (timestamp): When query was submitted

                    Relationships:
                    - query_logs.user_id → users.id

                    Common queries answered by this table:
                    - How many queries did admin run today?
                    - What are the most common questions asked?
                    - Which queries resulted in errors?
                    - What is the average pipeline response time?
                    - How often is the cache being hit?
                    """,
                "sql_reference": {
                    "table": "query_logs",
                    "key_columns": ["id", "user_id", "natural_language_query",
                                "generated_sql", "was_cache_hit", "execution_time_ms",
                                "row_count", "error_message", "created_at"]
                }
            },

            {
                "doc_id": "hierarchy_joins",
                "table_name": "users+transactions",
                "content": """
                    Join Pattern: Supervisor-to-Transactions (Multi-table)
                    Purpose: Describes how to query transactions belonging to ALL agents
                    under a specific supervisor. This is the most common multi-table pattern.

                    Pattern:
                    SELECT t.* 
                    FROM transactions t
                    JOIN users agent ON t.agent_id = agent.id
                    WHERE agent.parent_id = {supervisor_id}

                    Use this pattern when:
                    - Supervisor wants to see their team's transactions
                    - Comparing performance across agents in a team
                    - Getting team-level summaries

                    Agent-to-Supervisor lookup pattern:
                    SELECT u.full_name as agent, sup.full_name as supervisor
                    FROM users u
                    JOIN users sup ON u.parent_id = sup.id
                    WHERE u.role = 'agent'

                    Platform + Transactions join:
                    SELECT p.name, COUNT(t.id), SUM(t.amount)
                    FROM transactions t
                    JOIN platforms p ON t.platform_id = p.id
                    GROUP BY p.name

                    Common multi-table queries:
                    - Show me all transactions for supervisor virat's team
                    - Compare agent performance within a supervisor's team
                    - Which of supervisor rohit's agents has the most deposits?
                    - Show platform breakdown for each agent under supervisor hardik
                    """,
                "sql_reference": {
                    "joins": [
                        "transactions JOIN users ON transactions.agent_id = users.id",
                        "users supervisor JOIN users agent ON agent.parent_id = supervisor.id",
                        "transactions JOIN platforms ON transactions.platform_id = platforms.id"
                    ]
                }
            }
        ]