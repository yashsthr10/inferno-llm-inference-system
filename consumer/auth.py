from fastapi import Header, HTTPException, status
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import logging
import os # Used for graceful shutdown

# --- Setup Logging ---
# Configure logging for this module
logger = logging.getLogger("auth")

# --- Database Connection Pool Configuration ---
# It's better to initialize the pool once when the module is loaded,
# rather than connecting on each function call.
try:
    # Database connection URL
    POSTGRES_URL = 'postgresql://yash:secret@db:5432/users'
    
    # Initialize a simple connection pool.
    # minconn=1, maxconn=10 means the pool will start with 1 connection
    # and can grow up to 10 connections if needed.
    db_pool = SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=POSTGRES_URL
    )
    logger.info("✅ Database connection pool created successfully.")

except psycopg2.OperationalError as e:
    logger.error(f"❌ CRITICAL: Could not connect to database: {e}")
    db_pool = None # Set pool to None if connection fails

def _check_token_in_db(token: str):
    """
    Helper function to check if a token exists in the database using the connection pool.
    This is much more efficient than creating a new connection every time.
    """
    if not db_pool:
        # If the pool wasn't created, we can't check the database.
        logger.error("Database pool not available. Cannot authenticate token.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available."
        )

    conn = None
    try:
        # Get a connection from the pool
        conn = db_pool.getconn()
        # Use a `with` statement for the cursor to ensure it's closed automatically
        with conn.cursor() as cur:
            # FIX: Explicitly cast the database column to TEXT for comparison.
            # This resolves the "operator does not exist: character varying = uuid" error
            # by ensuring a text-to-text comparison, avoiding any ambiguous type inference
            # by PostgreSQL or the database driver.
            cur.execute("SELECT 1 FROM api_tokens WHERE token::text = %s", (token,))
            exists = cur.fetchone()

        # If the token does not exist in the database, `exists` will be None.
        if not exists:
            logger.warning(f"Authentication failed: Invalid or expired token provided: {token[:8]}...")
            # Use 401 Unauthorized for invalid credentials, as per convention.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token."
            )
        
        logger.info(f"Authentication successful for token: {token[:8]}...")

    except psycopg2.Error as e:
        # Catch any database-related errors
        logger.error(f"Database error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"A database error occurred during token verification: {e}"
        )
    finally:
        # IMPORTANT: Always return the connection to the pool
        if conn:
            db_pool.putconn(conn)


def verify_api_key(authorization: str = Header(None)):
    """
    FastAPI dependency function for HTTP header API key verification.
    It expects an 'Authorization' header in the format 'Bearer <token>'.
    """
    # Check if the Authorization header is provided and correctly formatted
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Authentication failed: Authorization header missing or malformed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed. Expected 'Bearer <token>'."
        )
    
    # Extract the token string from the header
    token = authorization.split(" ")[1]
    
    # Use the helper function to check the token against the database
    _check_token_in_db(token)
    
    # If _check_token_in_db does not raise an exception, the token is valid.
    return True # Return a value to satisfy FastAPI's dependency injection