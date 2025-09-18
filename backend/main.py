from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
import models, schemas, auth, models, database 
from sqlalchemy.orm import Session
import psycopg2
import uuid
import logging
import warnings
from models import APIToken
from datetime import timedelta
from typing import List
import io
import csv

# Add Prometheus monitoring
from prometheus_fastapi_instrumentator import Instrumentator

# Logging & warnings configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consumer")
warnings.simplefilter('ignore')

database.Base.metadata.create_all(bind=database.engine)
app = FastAPI()

# Instrumentator for Prometheus metrics
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update if your frontend runs elsewhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/signup", response_model=schemas.UserOut)
def signup(user_data: schemas.UserCreate, db: Session = Depends(auth.get_db)):
    # Check if user exists
    db_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = auth.get_password_hash(user_data.password)
    db_user = models.User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/login", response_model=schemas.UserOut)
def login(user_data: schemas.UserLogin, response: Response, db: Session = Depends(auth.get_db)):
    user = auth.authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    auth.set_jwt_cookie(response, access_token)
    return user


@app.post("/auth/refresh", response_model=schemas.UserOut)
def refresh_token(request: Request, response: Response, db: Session = Depends(auth.get_db)):
    user = auth.get_current_user_from_cookie(request, db)
    
    # Create new token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    auth.set_jwt_cookie(response, access_token)
    return user


@app.post("/auth/logout")
def logout(response: Response):
    auth.clear_jwt_cookie(response)
    return {"msg": "Logged out"}

@app.get("/me", response_model=schemas.UserOut)
def read_users_me(request: Request, db: Session = Depends(auth.get_db)):
    user = auth.get_current_user_from_cookie(request, db)
    return user
    
@app.post("/generate-token", response_model=schemas.TokenResponse)
def generate_api_token(token_data: schemas.TokenCreate, request: Request, db: Session = Depends(auth.get_db)):
    user = auth.get_current_user_from_cookie(request, db)
    
    # Generate unique token
    new_token = str(uuid.uuid4())
    
    # Create token record
    db_token = APIToken(
        token=new_token,
        name=token_data.name,
        user_id=user.id
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    
    return schemas.TokenResponse(token=new_token)

@app.get("/api/tokens", response_model=schemas.TokenList)
def list_tokens(request: Request, db: Session = Depends(auth.get_db)):
    user = auth.get_current_user_from_cookie(request, db)
    tokens = db.query(APIToken).filter(APIToken.user_id == user.id).all()
    return schemas.TokenList(tokens=tokens)

@app.delete("/api/tokens/{token_id}")
def delete_api_token(token_id: int, request: Request, db: Session = Depends(auth.get_db)):
    user = auth.get_current_user_from_cookie(request, db)
    
    token = db.query(APIToken).filter(
        APIToken.id == token_id,
        APIToken.user_id == user.id
    ).first()
    
    if not token:
        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )
    
    db.delete(token)
    db.commit()
    return {"message": "Token deleted successfully"}


# This is a synchronous helper function to run the database query
def bulk_insert_sync(db: Session, records: list, columns: tuple):
    string_buffer = io.StringIO()
    writer = csv.writer(string_buffer)
    writer.writerows(records)
    string_buffer.seek(0)

    # Get the raw database connection from the SQLAlchemy session
    raw_conn = db.connection().connection
    with raw_conn.cursor() as cursor:
        # Use the driver's high-performance COPY command
        cursor.copy_from(
            file=string_buffer,
            table='responses',
            sep=',',
            columns=columns
        )
    db.commit()

@app.post("/api/responses/batch")
async def create_batch_responses(
    feedback_items: List[schemas.FeedbackItem],
    db: Session = Depends(auth.get_db)
):
    if not feedback_items:
        raise HTTPException(status_code=400, detail="The batch cannot be empty.")

    # **Corrected data and column mapping**
    # Ensure the field name (e.g., item.model_name) matches the column name.
    records_to_insert = [
        (item.prompt, item.response, item.model_name, item.temperature, item.max_tokens)
        for item in feedback_items
    ]
    columns = ('prompt', 'response', 'model_name', 'temperature', 'max_tokens')

    try:
        # Run the synchronous database function in a separate thread
        # to avoid blocking the async application.
        await run_in_threadpool(
            bulk_insert_sync,
            db=db,
            records=records_to_insert,
            columns=columns
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during batch insert: {e}")

    return {
        "status": "success",
        "inserted_count": len(feedback_items)
    }