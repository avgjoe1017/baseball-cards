from database.models import SessionLocal, init_db


def test_db_connection():
    try:
        # Initialize the database schema
        init_db()

        # Test the connection by creating a session
        db = SessionLocal()
        db.execute("SELECT 1")  # Simple query to test connection
        db.close()
        print("Database connection successful and schema initialized.")
    except Exception as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    test_db_connection()
