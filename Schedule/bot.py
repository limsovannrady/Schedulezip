from bot_core import build_application

if __name__ == "__main__":
    application = build_application(with_job_queue=True)
    application.run_polling(drop_pending_updates=True)
