# Frontend Architecture

This frontend is built with **React** and serves as the user interface for authentication, dashboard, and API key management. It communicates with the backend and consumer services for user and AI operations.

## Structure
- **Entry Point:** `src/index.js`
- **Main App:** `src/App.jsx`
- **Component Folder:** `src/components/`
- **Styling:** CSS modules and global styles in `src/`

## Key Components
- `Navbar.jsx`: Navigation bar, handles login/logout links
- `Login.jsx` & `Signup.jsx`: User authentication forms
- `Dashboard.jsx`: Main user dashboard, displays API keys and user info
- `GeneratedKeyModal.jsx`: Modal for displaying newly generated API keys
- `Api.jsx`: Handles API requests and displays responses
- `ProtectedRoute.jsx`: Guards routes that require authentication
- `authContext.jsx`: React context for managing authentication state

## Authentication Flow
- User signs up or logs in via forms
- JWT is set in a secure cookie by the backend
- `authContext` tracks login state and user info
- Protected routes/components require authentication

## API Integration
- Uses `fetch` or `axios` to call backend endpoints for signup, login, token management, and AI completions
- Handles CORS and error states

## Usage
- Start with `npm start` (development) or build for production
- Configure backend/consumer URLs as needed in API calls

---
For more details, see the code and comments in each component. 