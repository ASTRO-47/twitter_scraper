from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from app.scraper import scrape_twitter
from app.models import TwitterScrapeResponse

class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(", ", ": "),
        ).encode("utf-8")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def form():
    return """
    <html>
    <head>
        <title>Twitter Scraper</title>
        <style>
            body {
                background: #f4f6fb;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background: #fff;
                padding: 2rem 2.5rem;
                border-radius: 12px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                text-align: center;
            }
            h2 {
                margin-bottom: 1.5rem;
                color: #1da1f2;
            }
            input[type='text'] {
                padding: 0.7rem 1rem;
                border: 1px solid #e1e8ed;
                border-radius: 6px;
                width: 220px;
                font-size: 1rem;
                margin-bottom: 1rem;
                outline: none;
                transition: border 0.2s;
            }
            input[type='text']:focus {
                border: 1.5px solid #1da1f2;
            }
            button {
                background: #1da1f2;
                color: #fff;
                border: none;
                border-radius: 6px;
                padding: 0.7rem 1.5rem;
                font-size: 1rem;
                cursor: pointer;
                transition: all 0.2s;
            }
            button:hover {
                background: #0d8ddb;
            }
            #result {
                margin-top: 20px;
                text-align: left;
                white-space: pre-wrap;
                font-family: monospace;
                max-height: 500px;
                overflow-y: auto;
                padding: 10px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Twitter Scraper</h2>
            <input id="username" type="text" placeholder="Enter Twitter username" required>
            <button onclick="scrape()">Scrape</button>
            <pre id="result"></pre>
        </div>

        <script>
        async function scrape() {
            const username = document.getElementById('username').value;
            const result = document.getElementById('result');
            result.textContent = 'Scraping in progress...';
            
            try {
                const response = await fetch(`/scrape/${encodeURIComponent(username)}`);
                const data = await response.json();
                result.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                result.textContent = `Error: ${error.message}`;
            }
        }
        </script>
    </body>
    </html>
    """

@app.get("/scrape/{username}")
async def scrape(username: str):
    try:
        result = await scrape_twitter(username)
        return JSONResponse(
            content=result,
            headers={
                "Content-Type": "application/json",
                "X-Content-Type-Options": "nosniff"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 