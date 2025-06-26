from fastapi import FastAPI, HTTPException
from app.scraper import scrape_twitter
from app.models import TwitterScrapeResponse

app = FastAPI()

@app.get("/scrape/{username}", response_model=TwitterScrapeResponse)
async def scrape(username: str):
    try:
        data = await scrape_twitter(username)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 