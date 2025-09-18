from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from pydantic import Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenCreate(BaseModel):
    name: str = "Default Key"

class TokenOut(BaseModel):
    id: int
    token: str
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    token: str

class TokenList(BaseModel):
    tokens: List[TokenOut]


class FeedbackItem(BaseModel):
    prompt: str
    response: str
    # Add these new optional fields
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # This is for Pydantic V1. If using V2, orm_mode is replaced by model_config
    class Config:
        orm_mode = True