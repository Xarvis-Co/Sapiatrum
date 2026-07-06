# Sapiatrum - Multi-Agent AI Task Routing Cluster

This project contains the backend and frontend for the Sapiatrum application.

## Overview

- **Backend**: A Python FastAPI application that implements a 5-step AI pipeline for processing user queries. It uses Perplexity, Claude, ChatGPT, and Gemini, along with Firebase for a learning loop.
- **Frontend**: A Flutter application that provides a UI for users to sign in, interact with the AI, and view chat history.

## Setup Instructions

### 1. Backend Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create a `.env` file** and add your API keys and GCP Project ID:
    ```
    GCP_PROJECT_ID="your-gcp-project-id"
    PERPLEXITY_API_KEY="your-perplexity-api-key"
    ANTHROPIC_API_KEY="your-anthropic-api-key"
    OPENAI_API_KEY="your-openai-api-key"
    GOOGLE_API_KEY="your-google-api-key"
    ```

3.  **Set up Google Cloud authentication** for the backend:
    ```bash
    gcloud auth application-default login
    ```

4.  **Build and run the Docker container:**
    ```bash
    docker build -t sapiatrum-backend .
    docker run -p 8080:8080 --env-file .env sapiatrum-backend
    ```
    Alternatively, for local development, install dependencies (`pip install -r requirements.txt`) and run `python main.py`.

### 2. Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Configure Firebase:**
    - Make sure you have the FlutterFire CLI installed: `dart pub global activate flutterfire_cli`
    - Run the configuration tool and follow the instructions:
    ```bash
    flutterfire configure
    ```
    This will generate a `lib/firebase_options.dart` file. Make sure to uncomment the Firebase initialization code in `lib/main.dart`.

3.  **Add Google Logo Asset:**
    - Create an `assets` directory inside the `frontend` directory.
    - Place a Google logo image named `google_logo.png` inside `frontend/assets`.

4.  **Get dependencies:**
    ```bash
    flutter pub get
    ```

5.  **Run the application:**
    ```bash
    flutter run
    ```
