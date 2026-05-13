# Nira AI Assistant - Copilot Instructions

Welcome to the Nira project. This document serves as a guide for AI coding assistants to quickly understand the project structure, language, and technical conventions. Nira is an intelligent product recommendation assistant (Pre-Search Decision Making) using conversational Persian interactions.

## 📚 Essential Documentation

- **[Technical Rules & Standards (MUST READ)](INSTRUCTIONS.md)**: Contains critical rules on SRP, naming conventions, module structure, and strict coding guidelines (RTL, docstrings in Persian).
- **[Project Overview & Vision](README.md)**: Details the MVP scope, what it does, and what's explicitly out of scope.
- **[System Architecture](ARCHITECTURE.md)**: Explains the layers, boundaries, and how components interact.
- **[Frontend & API Docs](FRONT_README.md)**: Contains contracts for REST and SSE components for integrating with stores.

## 🛠️ Tech Stack & Conventions

- **Language**: Python 3.11+ (using generic types and modern features like `Self`, `TaskGroup`.)
- **API Framework**: FastAPI, Pydantic, uvicorn.
- **Database & Storage**: SQLAlchemy 2 (Async), PostgreSQL (asyncpg), Alembic for migrations, and Qdrant for vector/hybrid search.
- **ML / AI Models**: ONNX (`optimum[onnxruntime]`) for embedding/reranker optimization, Groq/Google GenAI for LLM operations.
- **Modularity**: Strict separation of modules: Entry Points -> Business Logic -> Data. Each file must have only one responsibility (SRP).

## 🚀 Execution & Environment

- **Environment**: Virtual environment located at `.venv`
- **Run Backend Server (with reload)**:
    ```bash
    .\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload
    ```
- **Run Migrations (Alembic)**:
    ```bash
    .\.venv\Scripts\alembic.exe upgrade head
    ```

## 📝 Agent Instructions (Critical)

1. **Persian Content**: Ensure all docstrings are written in clear Persian. Do not use inline comments unless the logic is exceptionally complex. Ensure RTL characters are formatted properly if requested.
2. **Analysis Protocol**: Before generating code, analyze the request carefully, ensure all dependencies and components are clear based on `INSTRUCTIONS.md`.
3. **Link, don't embed**: Read existing documentation (`ARCHITECTURE.md`, `INSTRUCTIONS.md`) instead of expecting all rules to be duplicated here.
4. **Data Types**: All API models use strictly typed Pydantic structures.
