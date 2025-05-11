from unittest.mock import MagicMock, patch

import pytest

from database.models import get_session, init_db  # Changed SessionLocal to get_session


@pytest.mark.parametrize("db_response", [True, False])
def test_db_connection(db_response):
    # Patch get_session instead of SessionLocal
    # Patch where the names are looked up in *this* test file
    with patch("test_db_connection.get_session") as mock_get_session:
        # Mock the database session
        mock_session = MagicMock()
        if db_response:
            mock_session.execute.return_value = True  # Simulate successful query
        else:
            mock_session.execute.side_effect = Exception("Database connection failed")
        # Configure the mock get_session to return our mock session instance
        mock_get_session.return_value = mock_session
        try:
            # Initialize the database schema
            init_db()
            # Test the connection by getting a session via the function
            db = get_session()
            db.execute("SELECT 1")  # Simple query to test connection
            db.close()
            assert db_response, "Database connection should succeed"
        except Exception as e:
            assert not db_response, f"Expected failure but got: {e}"
