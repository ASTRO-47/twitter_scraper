from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.scraper import scrape_twitter
from app.models import TwitterScrapeResponse

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
            input[type='submit'] {
                background: #1da1f2;
                color: #fff;
                border: none;
                border-radius: 6px;
                padding: 0.7rem 1.5rem;
                font-size: 1rem;
                cursor: pointer;
                transition: background 0.2s;
            }
            input[type='submit']:hover {
                background: #0d8ddb;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Twitter Scraper</h2>
            <form action="/scrape" method="get">
                <input name="username" type="text" placeholder="Enter Twitter username" required><br>
                <input type="submit" value="Scrape">
            </form>
        </div>
    </body>
    </html>
    """

@app.get("/scrape", response_model=TwitterScrapeResponse)
async def scrape(username: str):
    try:
        # print(username)
        data = await scrape_twitter(username)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 