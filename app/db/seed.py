import os ,sys, psycopg2, random
import bcrypt
from datetime import datetime, timedelta, timezone
from faker import Faker
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.utils.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)
fake = Faker()
random.seed(42)
Faker.seed(42)


def hash_password(plain: str) -> str:
    """  Hash a password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def random_date(start_days_ago: int = 180, end_days_ago: int = 0):
    """Generate a random UTC datetime within the last 180 days."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def run_seed():
    logger.info("connecting to postgresql for seeding into tables...")

    connnection = psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        dbname=config.POSTGRES_DB
    )
    connnection.autocommit = False
    cur = connnection.cursor()

    try:
        logger.info("Running schema.sql...")
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r") as f:
            sql = f.read()
        cur.execute(sql)
        logger.info("schema created successfully.")

        logger.info("seeding admin user...")
        cur.execute("""
            INSERT INTO users (username, email, hashed_password, full_name, role, parent_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            "admin_dv",
            "dv.admin@dhaneshvashisth.com",
            hash_password("Admin@1234"),
            "Dhanesh Vashisth",
            "admin",
            None   
        ))
        admin_id = cur.fetchone()[0]
        logger.info("Admin created | id=%d", admin_id)

        supervisors_data = [
            ("supervisor_virat",  "virat.k@dhaneshvashisth.com",  "Virat Kohli"),
            ("supervisor_rohit",  "rohit.s@dhaneshvashisth.com",   "Rohit sharma"),
            ("supervisor_hardik",   "hardik.p@dhaneshvashisth.com",   "Hardik Pandya"),
        ]
        supervisor_ids = []
        logger.info("Seeding supervisors...")

        for username, email, full_name in supervisors_data:
            cur.execute("""
                INSERT INTO users (username, email, hashed_password, full_name, role, parent_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                username, email,
                hash_password("Super@1234"),
                full_name, "supervisor", admin_id
            ))
            sid = cur.fetchone()[0]
            supervisor_ids.append(sid)
            logger.info("Supervisor created | %s | id=%d", username, sid)

        agents_per_supervisor = {
            supervisor_ids[0]: [ 
                ("agent_dhoni",  "dhoni.m@dhaneshvashisth.com",  "Dhoni"),
                ("agent_sehwag",   "sehwag.v@dhaneshvashisth.com",   "Virender Sehwag"),
                ("agent_jaspreet",   "jaspreet.b@dhaneshvashisth.com",   "Jaspreet Bumrah"),
            ],
            supervisor_ids[1]: [  
                ("agent_surya",   "surya.y@dhaneshvashisth.com",   "S K Y"),
                ("agent_ishan",  "ishan.k@dhaneshvashisth.com",  "Ishan Kishan"),
                ("agent_abhishek",   "abhishek.s@dhaneshvashisth.com",   "Abhishek Sharma "),
            ],
            supervisor_ids[2]: [  
                ("agent_rahul",   "rahul.d@dhaneshvashisth.com",   "Rahul Dravid"),
                ("agent_sachin",   "sachin.t@dhaneshvashisth.com",   "Sachin Tendulkar"),
                ("agent_yuvraj",    "yuvraj.s@dhaneshvashisth.com",    "Yuvraj Singh"),
            ],
        }

        agent_ids = []
        logger.info("Seeding agents...")

        for sup_id, agents in agents_per_supervisor.items():
            for username, email, full_name in agents:
                cur.execute("""
                    INSERT INTO users (username, email, hashed_password, full_name, role, parent_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    username, email,
                    hash_password("Agent@1234"),
                    full_name, "agent", sup_id
                ))
                aid = cur.fetchone()[0]
                agent_ids.append(aid)
                logger.info("Agent created | %s | supervisor_id=%d | id=%d",
                            username, sup_id, aid)

        logger.info("Seeding platforms...")

        platforms = [
            ("4RABET",    "4BT"),
            ("1xCASINO",  "CAS"),
            ("BetNinja",  "BNJ"),
            ("MegaDice",  "MD"),
            ("PointsBet", "PB"),
        ]
        platform_ids = []

        for name, code in platforms:
            cur.execute("""
                INSERT INTO platforms (name, code)
                VALUES (%s, %s)
                RETURNING id
            """, (name, code))
            pid = cur.fetchone()[0]
            platform_ids.append(pid)

        logger.info("Platforms seeded: %s", [p[0] for p in platforms])

        logger.info("Seeding transactions (~500 rows)...")

        txn_types   = ["deposit", "withdrawal", "bonus", "adjustment"]
        txn_weights = [0.50, 0.30, 0.15, 0.05]  
        statuses    = ["completed", "pending", "failed", "reversed"]
        stat_weights= [0.70, 0.15, 0.10, 0.05]  

        txn_count = 0
        for agent_id in agent_ids:
            num_txns = random.randint(50, 60)

            for _ in range(num_txns):
                txn_type = random.choices(txn_types, txn_weights)[0]
                status   = random.choices(statuses,  stat_weights)[0]
                created  = random_date(start_days_ago=180)

                processed = None
                if status != "pending":
                    processed = created + timedelta(
                        minutes=random.randint(1, 120)
                    )

                if txn_type == "deposit":
                    amount = round(random.uniform(50, 5000), 2)
                elif txn_type == "withdrawal":
                    amount = round(random.uniform(20, 3000), 2)
                elif txn_type == "bonus":
                    amount = round(random.uniform(5, 500), 2)
                else:
                    amount = round(random.uniform(1, 200), 2)

                cur.execute("""
                    INSERT INTO transactions (
                        reference_code, agent_id, platform_id,
                        customer_name, customer_phone,
                        amount, transaction_type, status,
                        created_at, processed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    f"TXN-{fake.unique.bothify(text='????-########').upper()}",
                    agent_id,
                    random.choice(platform_ids),
                    fake.name(),
                    fake.phone_number()[:15],
                    amount,
                    txn_type,
                    status,
                    created,
                    processed
                ))
                txn_count += 1

        logger.info("Transactions seeded | total=%d", txn_count)

        # ------commit everything-------------------
        connnection.commit()
        logger.info("=" * 50)
        logger.info("DATABASE SEEDING COMPLETE")
        logger.info("Admin    : 1  | login: admin_dv / Admin@1234")
        logger.info("Supervisors: 3 | login: supervisor_priya / Super@1234")
        logger.info("Agents   : 9  | login: agent_aditya / Agent@1234")
        logger.info("Platforms: 5")
        logger.info("Transactions: %d", txn_count)
        logger.info("=" * 50)

    except Exception as e:
        connnection.rollback()
        logger.error("Seeding failed — rolled back | error: %s", str(e))
        raise
    finally:
        cur.close()
        connnection.close()


if __name__ == "__main__":
    run_seed()