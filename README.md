# FastAPI Twitter Scraper

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

2. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```

## Usage

- Endpoint: `GET /scrape/{username}`
- Example: `http://localhost:8000/scrape/srikanthc767`

Returns structured JSON with user profile, tweets (with screenshots), followers, and following.

---

**Note:**
- Screenshots are saved in the `screenshots/` directory.
- The scraper uses Playwright in headless mode.
- For now, retweets and likes are skipped. 