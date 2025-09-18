# Backend Service

This backend is built with **FastAPI** and provides authentication, user management, and API token generation for a full-stack application. It interacts with a PostgreSQL database and supports secure communication with the frontend and other services.

## Architecture Overview
- **Framework:** FastAPI
- **Database:** PostgreSQL (via SQLAlchemy ORM)
- **Authentication:** JWT-based, with secure cookie storage
- **API Token Management:** Issue and manage API tokens for external access
- **CORS:** Configured for frontend communication

## Key Components
- `main.py`: FastAPI app, route definitions for signup, login, token management, and batch operations.
- `auth.py`: Authentication logic, password hashing, JWT creation, and cookie handling.
- `models.py`: SQLAlchemy models for users and API tokens.
- `schemas.py`: Pydantic schemas for request/response validation.
- `database.py`: Database connection and session management.

## Main Endpoints
- `POST /signup`: Register a new user
- `POST /login`: Authenticate and set JWT cookie
- `POST /auth/refresh`: Refresh JWT token
- `POST /auth/logout`: Clear JWT cookie
- `GET /me`: Get current user info
- `POST /generate-token`: Generate new API token
- `GET /api/tokens`: List API tokens
- `DELETE /api/tokens/{token_id}`: Delete an API token
- `POST /api/responses/batch`: Batch insert feedback/responses

## Database
- Tables for users and API tokens
- Uses SQLAlchemy ORM for all DB operations

## Security
- Passwords are hashed using a secure algorithm
- JWT tokens are stored in HTTP-only cookies
- CORS is restricted to trusted frontend origins

## Usage
- Start with `uvicorn main:app --reload`
- Configure DB and CORS as needed in `main.py`

---
For more details, see the code and comments in each file. 