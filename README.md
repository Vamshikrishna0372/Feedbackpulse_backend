# FeedbackPulse Backend

This README contains specific instructions to setup, run, and deploy the backend.

## Run Instructions (Local)

1.  **Navigate** to the `backend` directory.

    ```bash
    cd backend
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**

    ```bash
    python -m uvicorn app.main:app --reload
    ```
    
    The API will be available at `http://localhost:8000`.

## Deployment Instructions

To deploy to Render, Railway, or similar platforms:

1.  **Set Environment Variables**:
    Configure these in your hosting dashboard:
    *   `MONGODB_URI`: Your MongoDB connection string.
    *   `JWT_SECRET`: A secure random string.
    *   `JWT_EXPIRE_MINUTES`: E.g., `60`.
    *   `ENVIRONMENT`: Set to `production`.
    *   `ALLOWED_ORIGINS`: Comma-separated list of allowed frontend URLs (e.g., `https://your-frontend.com`).

2.  **Start Command**:
    The platform should use the `Procfile` automatically, or you can specify:
    ```bash
    python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
    ```

3.  **Health Check**:
    Verify deployment at `/health`.
