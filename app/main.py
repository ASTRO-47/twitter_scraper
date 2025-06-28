from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import json
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
                min-width: 120px;
            }
            button:hover:not(:disabled) {
                background: #0d8ddb;
            }
            button:disabled {
                background: #9fd0f1;
                cursor: not-allowed;
            }
            .loading {
                display: none;
                margin-top: 1rem;
                color: #1da1f2;
            }
            .spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #1da1f2;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-right: 8px;
                vertical-align: middle;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Twitter Scraper</h2>
            <form id="scrapeForm" onsubmit="handleSubmit(event)">
                <input name="username" type="text" placeholder="Enter Twitter username" required><br>
                <button type="submit" id="scrapeButton">Scrape</button>
            </form>
            <div id="loading" class="loading">
                <div class="spinner"></div>
                <span>Scraping in progress...</span>
            </div>
        </div>

        <script>
        async function handleSubmit(event) {
            event.preventDefault();
            
            const form = event.target;
            const button = document.getElementById('scrapeButton');
            const loading = document.getElementById('loading');
            const username = form.username.value;
            
            // Disable button and show loading
            button.disabled = true;
            loading.style.display = 'block';
            
            try {
                const response = await fetch(`/scrape?username=${encodeURIComponent(username)}`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to scrape data');
                }
                
                // Handle successful response
                console.log('Scraping completed:', data);
                alert('Scraping completed successfully!');
                
            } catch (error) {
                console.error('Error:', error);
                alert('Error: ' + error.message);
            } finally {
                // Re-enable button and hide loading
                button.disabled = false;
                loading.style.display = 'none';
            }
        }
        </script>
    </body>
    </html>
    """

@app.get("/scrape", response_model=TwitterScrapeResponse, response_class=PrettyJSONResponse)
async def scrape(username: str):
    try:
        data = await scrape_twitter(username)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 