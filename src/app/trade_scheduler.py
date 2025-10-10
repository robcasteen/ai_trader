from scheduler_instance import scheduler
from main import run_trade_cycle
from dashboard import app
import uvicorn
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timedelta

# Schedule the trading job
scheduler.add_job(
    run_trade_cycle,
    trigger=IntervalTrigger(minutes=5),
    id="trade_job",
    name="run_trade_cycle",
    replace_existing=True,
)

scheduler.start()
print("[Scheduler] Running GPT sentiment strategy every 5 minutes...")

# Start the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
