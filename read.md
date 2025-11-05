## Authentication & Google Sign-In

- Set `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend) to the same OAuth client ID created for Google Identity Services.
- Provide `CLIENT_SECRET` only if reusing the legacy `login/` FastAPI module; the primary flow validates Google ID tokens from the frontend.
- Configure `JWT_SECRET` (backend) for signing session tokens. Optionally override `JWT_ALGORITHM` and `JWT_EXP_MINUTES`.
- Start the backend (`uvicorn llm_api:app`) and frontend (`npm run dev` in `frontend/`). The React app now prompts for Google login before exposing receipt tools.
- After signing in, requests automatically include the issued JWT via the `Authorization` header; use the “Log out” button in the header to clear state.
