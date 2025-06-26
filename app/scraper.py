import os
from typing import List, Dict
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

async def scrape_user_profile(page, username: str) -> Dict:
    await page.goto(f"https://x.com/{username}")
    await page.wait_for_selector('div[data-testid="UserName"]', timeout=10000)
    name = await page.locator('div[data-testid="UserName"] span').nth(0).inner_text()
    bio = ""
    try:
        bio = await page.locator('div[data-testid="UserDescription"]').inner_text()
    except:
        bio = ""
    return {"username": name, "bio": bio}

async def scrape_tweets(page, username: str) -> List[Dict]:
    await page.goto(f"https://x.com/{username}")
    await page.wait_for_selector('article', timeout=10000)
    tweets = []
    tweet_elements = await page.locator('article').all()
    for i, tweet in enumerate(tweet_elements[:5]):  # Get up to 5 tweets
        try:
            content = await tweet.locator('div[lang]').inner_text()
        except:
            content = ""
        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_tweet{i+1}.png")
        await tweet.screenshot(path=screenshot_path)
        tweets.append({
            "tweet_content": content,
            "tweet_screenshot": screenshot_path
        })
    return tweets

async def scrape_followers(page, username: str) -> List[Dict]:
    await page.goto(f"https://x.com/{username}/followers")
    await page.wait_for_selector('div[dir="ltr"] > span', timeout=10000)
    followers = []
    follower_cards = await page.locator('div[dir="ltr"] > span').all()
    for card in follower_cards[:5]:  # Get up to 5 followers
        try:
            name = await card.inner_text()
            bio = ""
        except:
            name = ""
            bio = ""
        followers.append({
            "follower_name": name,
            "follower_bio": bio
        })
    return followers

async def scrape_following(page, username: str) -> List[Dict]:
    await page.goto(f"https://x.com/{username}/following")
    await page.wait_for_selector('div[dir="ltr"] > span', timeout=10000)
    following = []
    following_cards = await page.locator('div[dir="ltr"] > span').all()
    for card in following_cards[:5]:  # Get up to 5 following
        try:
            name = await card.inner_text()
            bio = ""
        except:
            name = ""
            bio = ""
        following.append({
            "following_name": name,
            "following_bio": bio
        })
    return following

async def scrape_twitter(username: str) -> Dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(f"https://x.com/{username}")
        user_profile = await scrape_user_profile(page, username)
        tweets = await scrape_tweets(page, username)
        followers = await scrape_followers(page, username)
        following = await scrape_following(page, username)
        await browser.close()
        return {
            "user_profile": user_profile,
            "tweets": tweets,
            "followers": followers,
            "following": following
        } 