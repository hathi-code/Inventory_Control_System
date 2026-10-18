# Intelligent Inventory Control System

A multi-agent system for inventory forecasting and automated procurement,
with real-time alerts and an admin approval workflow.

## Features
- Demand forecasting with Scikit-Learn
- Multi-agent pipeline (forecasting, procurement, coordinator, scheduler)
- JWT authentication with admin and staff roles
- Real-time updates over WebSockets
- Email alerts for orders needing approval

## Tech Stack
Python, FastAPI, PostgreSQL, SQLAlchemy, Scikit-Learn, Docker

## Setup
1. Clone the repo
2. Create a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your values
5. Copy `docker-compose.example.yml` to `docker-compose.yml` and fill in your values
6. Start the database: `docker compose up -d db`
7. Run the app: `uvicorn main:app --reload`

## Tests
`pytest`