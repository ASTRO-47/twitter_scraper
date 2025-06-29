from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import json
import os
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
            /* Spinner overlay styles */
            #spinnerOverlay {
                display: none;
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(255,255,255,0.7);
                z-index: 9999;
                justify-content: center;
                align-items: center;
            }
            .spinner {
                border: 6px solid #e1e8ed;
                border-top: 6px solid #1da1f2;
                border-radius: 50%;
                width: 48px;
                height: 48px;
                animation: spin 1s linear infinite;
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
            <input id="username" type="text" placeholder="Enter Twitter username" required>
            <button onclick="scrape()">Scrape</button>
            <pre id="result"></pre>
            <div id="screenshotsLink" style="display: none; margin-top: 20px;">
                <a id="viewScreenshotsBtn" href="#" style="color: #1da1f2; text-decoration: none; font-weight: bold; font-size: 16px; padding: 10px 20px; border: 2px solid #1da1f2; border-radius: 6px; display: inline-block;">
                    📸 View Screenshots for this User
                </a>
            </div>
        </div>
        <div id="spinnerOverlay">
            <div class="spinner"></div>
        </div>
        <script>
        let currentAbortController = null;
        function showSpinner(show) {
            document.getElementById('spinnerOverlay').style.display = show ? 'flex' : 'none';
        }
        async function scrape() {
            const username = document.getElementById('username').value;
            const result = document.getElementById('result');
            const screenshotsLink = document.getElementById('screenshotsLink');
            if (!username.trim()) {
                result.textContent = 'Please enter a username';
                return;
            }
            // Abort any previous fetch
            if (currentAbortController) currentAbortController.abort();
            const abortController = new AbortController();
            currentAbortController = abortController;
            showSpinner(true);
            result.textContent = 'Scraping in progress...';
            screenshotsLink.style.display = 'none';
            try {
                const response = await fetch(`/scrape/${encodeURIComponent(username)}`, { signal: abortController.signal });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                result.textContent = JSON.stringify(data, null, 2);
                const viewScreenshotsBtn = document.getElementById('viewScreenshotsBtn');
                viewScreenshotsBtn.href = `/view-screenshots/${username}`;
                screenshotsLink.style.display = 'block';
            } catch (error) {
                if (error.name === 'AbortError') {
                    result.textContent = 'Scraping cancelled.';
                } else {
                    result.textContent = `Error: ${error.message}`;
                }
                screenshotsLink.style.display = 'none';
            } finally {
                showSpinner(false);
                currentAbortController = null;
            }
        }
        // Cancel fetch if user refreshes or leaves
        window.addEventListener('beforeunload', function() {
            if (currentAbortController) currentAbortController.abort();
        });
        document.getElementById('username').addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                scrape();
            }
        });
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

@app.get("/screenshots/{username}")
async def get_screenshots(username: str):
    """Get list of screenshots for a specific user"""
    screenshots_dir = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
    user_screenshots = []
    
    if os.path.exists(screenshots_dir):
        for filename in os.listdir(screenshots_dir):
            if filename.startswith(f"{username}_"):
                user_screenshots.append(filename)
    
    return JSONResponse(content={"screenshots": user_screenshots})

@app.get("/screenshot/{filename}")
async def get_screenshot(filename: str):
    """Serve a specific screenshot file"""
    screenshots_dir = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
    file_path = os.path.join(screenshots_dir, filename)
    
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    else:
        raise HTTPException(status_code=404, detail="Screenshot not found")

@app.get("/view-screenshots/{username}")
async def view_screenshots_page(username: str):
    """Simple page to view screenshots for a user"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Screenshots for @{username}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .screenshots {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
                max-width: 1200px;
                margin: 0 auto;
            }}
            .screenshot {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .screenshot img {{
                width: 100%;
                height: auto;
                border-radius: 4px;
                cursor: pointer;
            }}
            .screenshot .name {{
                margin-top: 10px;
                font-size: 14px;
                color: #666;
                text-align: center;
            }}
            .modal {{
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.9);
            }}
            .modal img {{
                margin: auto;
                display: block;
                max-width: 90%;
                max-height: 90%;
                margin-top: 5%;
            }}
            .close {{
                position: absolute;
                top: 15px;
                right: 35px;
                color: white;
                font-size: 40px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Screenshots for @{username}</h1>
            <a href="/" style="color: #1da1f2; text-decoration: none;">← Back to Scraper</a>
        </div>
        
        <div id="screenshots" class="screenshots">
            <p>Loading screenshots...</p>
        </div>
        
        <div id="modal" class="modal">
            <span class="close">&times;</span>
            <img id="modalImg">
        </div>
        
        <script>
        async function loadScreenshots() {{
            try {{
                const response = await fetch('/screenshots/{username}');
                const data = await response.json();
                
                const container = document.getElementById('screenshots');
                if (data.screenshots && data.screenshots.length > 0) {{
                    container.innerHTML = '';
                    data.screenshots.forEach(screenshot => {{
                        const div = document.createElement('div');
                        div.className = 'screenshot';
                        div.innerHTML = `
                            <img src="/screenshot/${{screenshot}}" alt="${{screenshot}}" onclick="openModal(this.src)">
                            <div class="name">${{screenshot}}</div>
                        `;
                        container.appendChild(div);
                    }});
                }} else {{
                    container.innerHTML = '<p>No screenshots found for this user.</p>';
                }}
            }} catch (error) {{
                document.getElementById('screenshots').innerHTML = '<p>Error loading screenshots.</p>';
            }}
        }}
        
        function openModal(src) {{
            document.getElementById('modalImg').src = src;
            document.getElementById('modal').style.display = 'block';
        }}
        
        document.querySelector('.close').onclick = function() {{
            document.getElementById('modal').style.display = 'none';
        }}
        
        window.onclick = function(event) {{
            const modal = document.getElementById('modal');
            if (event.target == modal) {{
                modal.style.display = 'none';
            }}
        }}
        
        loadScreenshots();
        </script>
    </body>
    </html>
    """)
