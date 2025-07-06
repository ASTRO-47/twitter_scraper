from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response, StreamingResponse
import json
import os
from fastapi.middleware.cors import CORSMiddleware
from app.scraper import scrape_twitter
from app.models import TwitterScrapeResponse
import img2pdf
from io import BytesIO

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
                padding: 3rem 4rem;
                border-radius: 16px;
                box-shadow: 0 4px 32px rgba(0,0,0,0.10);
                text-align: center;
                min-width: 400px;
                max-width: 600px;
            }
            h2 {
                margin-bottom: 2rem;
                color: #1da1f2;
                font-size: 2.2rem;
            }
            input[type='text'] {
                padding: 1rem 1.5rem;
                border: 1.5px solid #e1e8ed;
                border-radius: 8px;
                width: 320px;
                font-size: 1.2rem;
                margin-bottom: 1.5rem;
                outline: none;
                transition: border 0.2s;
            }
            input[type='text']:focus {
                border: 2px solid #1da1f2;
            }
            button {
                background: #1da1f2;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 1rem 2.5rem;
                font-size: 1.2rem;
                cursor: pointer;
                transition: all 0.2s;
                margin-bottom: 1rem;
            }
            button:hover {
                background: #0d8ddb;
            }
            #result {
                margin-top: 28px;
                text-align: left;
                white-space: pre-wrap;
                font-family: monospace;
                max-height: 600px;
                overflow-y: auto;
                padding: 16px;
                font-size: 1.08rem;
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
                width: 56px;
                height: 56px;
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
async def get_screenshots(username: str, list: int = Query(0, description="Return list instead of PDF")):
    """Return a PDF of all screenshots for a specific user, or a list if ?list=1"""
    screenshots_dir = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
    user_screenshots = []
    if os.path.exists(screenshots_dir):
        for filename in sorted(os.listdir(screenshots_dir)):
            if filename.startswith(f"{username}_") and filename.lower().endswith('.png'):
                user_screenshots.append(filename if list else os.path.join(screenshots_dir, filename))
    if not user_screenshots:
        # Return a simple HTML error if accessed from browser
        return Response(
            content=f"<html><body><h2>No screenshots found for @{username}.</h2><a href='/view-screenshots/{username}'>Back</a></body></html>",
            status_code=404,
            media_type="text/html"
        )
    if list:
        return JSONResponse(content={"screenshots": user_screenshots})
    # Create PDF in memory
    pdf_bytes = BytesIO()
    try:
        pdf_bytes.write(img2pdf.convert(user_screenshots))
        pdf_bytes.seek(0)
    except Exception as e:
        return Response(
            content=f"<html><body><h2>Error creating PDF: {str(e)}</h2><a href='/view-screenshots/{username}'>Back</a></body></html>",
            status_code=500,
            media_type="text/html"
        )
    headers = {
        "Content-Disposition": f"attachment; filename={username}_screenshots.pdf"
    }
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers=headers
    )

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
            .download-btn {{
                display: inline-block;
                margin-bottom: 30px;
                padding: 12px 28px;
                background: #1da1f2;
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 1.1rem;
                font-weight: bold;
                text-decoration: none;
                transition: background 0.2s;
            }}
            .download-btn:hover {{
                background: #0d8ddb;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Screenshots for @{username}</h1>
            <a href="/" style="color: #1da1f2; text-decoration: none;">← Back to Scraper</a><br><br>
            <a class="download-btn" href="/screenshots/{username}" download>⬇️ Download All as PDF</a>
            <div style="margin-top:10px;color:#888;font-size:14px;">If the download fails or the file is not a PDF, right-click and choose 'Save link as...'</div>
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
                const response = await fetch('/screenshots/{username}?list=1');
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

@app.get("/scraped/{filename}")
async def get_scraped_profile(filename: str):
    scraped_dir = os.path.join(os.path.dirname(__file__), '..', 'scraped_profiles')
    file_path = os.path.join(scraped_dir, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/json")
    else:
        raise HTTPException(status_code=404, detail="File not found")
