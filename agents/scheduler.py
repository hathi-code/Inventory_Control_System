from apscheduler.schedulers.background import BackgroundScheduler
from agents.coordinator import run_agent_pipeline


def start_scheduler():
    """THE TRIGGER. Runs run_agent_pipeline() automatically every
    6 hours, with no human or API call needed to kick it off.
    Call this once when FastAPI starts (see main.py)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_agent_pipeline, "interval", hours=6)
    scheduler.start()
    return scheduler
