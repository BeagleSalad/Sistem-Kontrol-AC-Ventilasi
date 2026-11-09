from pathlib import Path
from app.database import get_connection
with get_connection() as connection:
    connection.execute(Path("migrations/001_initial_postgres.sql").read_text())
print("Migration applied.")
