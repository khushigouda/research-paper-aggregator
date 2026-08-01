import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

# Ensure root folder is in sys.path
root_dir = str(Path(__file__).parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

load_dotenv(override=True)

from app.database.create_tables import create_all_tables
from app.services.pipeline_runner import WeeklyPipelineRunner

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/run-digest":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Starting weekly digest pipeline in background...\n")
            threading.Thread(target=run_pipeline_bg).start()
            return

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = """
        <!DOCTYPE html>
        <html>
            <head>
                <title>AI Research Paper Aggregator Service</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px 20px; }
                    .card { background: #1e293b; padding: 40px; border-radius: 12px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
                    h1 { color: #38bdf8; font-size: 24px; margin-bottom: 10px; }
                    p { color: #94a3b8; font-size: 15px; margin-bottom: 30px; }
                    .btn { background: #6366f1; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block; transition: all 0.2s; }
                    .btn:hover { background: #4f46e5; }
                    .status { display: inline-block; padding: 6px 12px; background: #10b98120; color: #10b981; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="status">● Service Online</div>
                    <h1>AI Research Paper Aggregator</h1>
                    <p>Connected to Supabase PostgreSQL & Gemini AI pipeline.</p>
                    <a href="/run-digest" class="btn">🚀 Trigger Weekly Digest Now</a>
                </div>
            </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

def run_pipeline_bg():
    try:
        print("🚀 [Render Web Service] Executing weekly paper digest pipeline...")
        my_email = os.getenv("MY_EMAIL")
        if not my_email:
            print("❌ Error: MY_EMAIL environment variable is missing.")
            return
        
        runner = WeeklyPipelineRunner()
        results = runner.run(
            user_email=my_email,
            topic="Machine Learning",
            user_name="Khushi",
            top_n=3,
            time_range="1 week",
            fetch_limit=5
        )
        print(f"✅ [Render Web Service] Pipeline completed: {results}")
    except Exception as e:
        print(f"❌ [Render Web Service] Pipeline error: {e}")

def main():
    print("🚀 Initializing database tables...")
    try:
        create_all_tables()
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")

    port = int(os.getenv("PORT", 10000))
    print(f"🌐 Starting web server on port {port}...")
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    
    # Run pipeline once on startup
    threading.Thread(target=run_pipeline_bg).start()
    
    server.serve_forever()

if __name__ == "__main__":
    main()
