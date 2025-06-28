import os
import json
import asyncio
from typing import List, Dict
from playwright.async_api import async_playwright, TimeoutError

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), 'twitter_cookies.json')

async def safe_wait_for_selector(page, selector, timeout=10000, description="element"):
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except TimeoutError:
        print(f"Timeout waiting for {description}")
        return False
    except Exception as e:
        print(f"Error waiting for {description}: {str(e)}")
        return False

async def scrape_user_profile(page, username: str) -> dict:
    try:
        await page.goto(f"https://twitter.com/{username}")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)
        
        if not await safe_wait_for_selector(page, 'div[data-testid="UserName"]', description="profile"):
            return {"username": username, "bio": ""}
        
        display_name = await page.locator('div[data-testid="UserName"] span').nth(0).inner_text()
        try:
            bio = await page.locator('div[data-testid="UserDescription"]').inner_text()
        except:
            bio = ""
        return {"username": display_name, "bio": bio}
    except Exception as e:
        print(f"Error scraping profile: {str(e)}")
        return {"username": username, "bio": ""}

async def scrape_tweets(page, username: str) -> List[Dict]:
    tweets = []
    try:
        if page.url != f"https://twitter.com/{username}":
            await page.goto(f"https://twitter.com/{username}")
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)
        
        if not await safe_wait_for_selector(page, 'article', description="tweets"):
            return tweets
        
        tweet_elements = await page.locator('article').all()
        for i, tweet in enumerate(tweet_elements[:5]):
            try:
                # Try to get tweet text
                try:
                    content_element = tweet.locator('div[data-testid="tweetText"]').first
                    content = await content_element.inner_text()
                except Exception as e:
                    print(f"Could not get tweet text for tweet {i+1}: {str(e)}")
                    content = ""
                
                # Try to get screenshot
                try:
                    screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_tweet{i+1}.png")
                    await tweet.screenshot(path=screenshot_path)
                except Exception as e:
                    print(f"Could not get screenshot for tweet {i+1}: {str(e)}")
                    screenshot_path = ""
                
                # Only add tweet if we got either content or screenshot
                if content or screenshot_path:
                    tweets.append({
                        "tweet_content": content,
                        "tweet_screenshot": screenshot_path
                    })
            except Exception as e:
                print(f"Error processing tweet {i+1}: {str(e)}")
                continue
    except Exception as e:
        print(f"Error scraping tweets: {str(e)}")
    return tweets

async def scrape_likes(page, username: str) -> List[Dict]:
    likes = []
    try:
        await page.goto(f"https://twitter.com/{username}/likes")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)
        
        if not await safe_wait_for_selector(page, 'article', description="likes"):
            return likes
        
        liked_tweets = await page.locator('article').all()
        for i, tweet in enumerate(liked_tweets[:5]):
            try:
                content_element = tweet.locator('div[data-testid="tweetText"]').first
                content = await content_element.inner_text()
                
                name_element = tweet.locator('div[data-testid="User-Name"] > div:first-child > div:first-child > span').first
                username = await name_element.inner_text()
                
                try:
                    bio_element = tweet.locator('div[data-testid="UserDescription"]').first
                    bio = await bio_element.inner_text()
                except:
                    bio = ""
                
                screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_like{i+1}.png")
                await tweet.screenshot(path=screenshot_path)
                
                likes.append({
                    "liked_tweet_content": content,
                    "liked_tweet_username": username,
                    "liked_tweet_profile_bio": bio,
                    "liked_tweet_screenshot": screenshot_path,
                    "liked_main_content": content
                })
            except Exception as e:
                print(f"Error processing like {i+1}: {str(e)}")
                continue
            
            if len(likes) >= 5:
                break
                
    except Exception as e:
        print(f"Error scraping likes: {str(e)}")
    return likes

async def scrape_followers(page, username: str) -> List[Dict]:
    followers = []
    try:
        await page.goto(f"https://twitter.com/{username}/followers")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)
        
        if not await safe_wait_for_selector(page, 'div[data-testid="cellInnerDiv"]', description="followers"):
            return followers
        
        await page.wait_for_selector('div[data-testid="UserCell"]', timeout=10000)
        
        follower_cards = await page.locator('div[data-testid="UserCell"]').all()
        for i, card in enumerate(follower_cards[:5]):
            try:
                name_element = card.locator('div[data-testid="User-Name"] > div:first-child > div:first-child > span').first
                name = await name_element.inner_text()
                
                try:
                    bio_element = card.locator('div[data-testid="UserDescription"]').first
                    bio = await bio_element.inner_text()
                except:
                    bio = ""
                
                if name:
                    followers.append({
                        "follower_name": name,
                        "follower_bio": bio
                    })
            except Exception as e:
                print(f"Error processing follower {i+1}: {str(e)}")
                continue
            
            if len(followers) >= 5:
                break
                
    except Exception as e:
        print(f"Error scraping followers: {str(e)}")
    return followers

async def scrape_following(page, username: str) -> List[Dict]:
    following = []
    try:
        await page.goto(f"https://twitter.com/{username}/following")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)
        
        if not await safe_wait_for_selector(page, 'div[data-testid="cellInnerDiv"]', description="following"):
            return following
        
        await page.wait_for_selector('div[data-testid="UserCell"]', timeout=10000)
        
        following_cards = await page.locator('div[data-testid="UserCell"]').all()
        for i, card in enumerate(following_cards[:5]):
            try:
                name_element = card.locator('div[data-testid="User-Name"] > div:first-child > div:first-child > span').first
                name = await name_element.inner_text()
                
                try:
                    bio_element = card.locator('div[data-testid="UserDescription"]').first
                    bio = await bio_element.inner_text()
                except:
                    bio = ""
                
                if name:
                    following.append({
                        "following_name": name,
                        "following_bio": bio
                    })
            except Exception as e:
                print(f"Error processing following {i+1}: {str(e)}")
                continue
            
            if len(following) >= 5:
                break
                
    except Exception as e:
        print(f"Error scraping following: {str(e)}")
    return following

async def scrape_retweets(page, username: str) -> List[Dict]:
    retweets = []
    try:
        if page.url != f"https://twitter.com/{username}":
            await page.goto(f"https://twitter.com/{username}")
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)
        
        if not await safe_wait_for_selector(page, 'article', description="retweets"):
            return retweets
        
        tweet_elements = await page.locator('article').all()
        for i, tweet in enumerate(tweet_elements[:10]):
            try:
                # Check if it's a retweet
                retweet_indicator = tweet.locator('span:has-text("Reposted")')
                if not await retweet_indicator.count():
                    continue
                
                # Try to get content
                try:
                    content_element = tweet.locator('div[data-testid="tweetText"]').first
                    content = await content_element.inner_text()
                except Exception as e:
                    print(f"Could not get retweet text for retweet {i+1}: {str(e)}")
                    content = ""
                
                # Try to get username
                try:
                    name_element = tweet.locator('div[data-testid="User-Name"] > div:first-child > div:first-child > span').first
                    username = await name_element.inner_text()
                except Exception as e:
                    print(f"Could not get username for retweet {i+1}: {str(e)}")
                    username = ""
                
                # Try to get screenshot
                try:
                    screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_retweet{i+1}.png")
                    await tweet.screenshot(path=screenshot_path)
                except Exception as e:
                    print(f"Could not get screenshot for retweet {i+1}: {str(e)}")
                    screenshot_path = ""
                
                # Try to get original content
                try:
                    main_content_element = tweet.locator('div[data-testid="tweetText"]').nth(1)
                    main_content = await main_content_element.inner_text()
                except Exception as e:
                    print(f"Could not get original content for retweet {i+1}: {str(e)}")
                    main_content = content
                
                # Only add retweet if we got some content
                if content or username or screenshot_path:
                    retweets.append({
                        "retweet_content": content,
                        "retweet_username": username,
                        "retweet_screenshot": screenshot_path,
                        "retweet_main_content": main_content
                    })
                
                if len(retweets) >= 5:
                    break
            except Exception as e:
                print(f"Error processing retweet {i+1}: {str(e)}")
                continue
    except Exception as e:
        print(f"Error scraping retweets: {str(e)}")
    return retweets

async def scrape_twitter(username: str) -> Dict:
    # Initialize result dictionary with empty values
    result = {
    "user_profile": {"username": username, "bio": ""},
    "tweets": [],
    "retweets": []
}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            
            if os.path.exists(COOKIES_FILE):
                try:
                    with open(COOKIES_FILE, "r") as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    print("Cookies loaded successfully")
                except Exception as e:
                    print(f"Error loading cookies: {str(e)}")
                    return result
            else:
                print("No cookies file found. Please run login_manual.py first")
                return result
            
            page = await context.new_page()
            page.set_default_timeout(30000)  # 30 seconds timeout
            
            try:
                # Verify login
                await page.goto("https://twitter.com/home", wait_until="load")
                await asyncio.sleep(2)
                
                if not await safe_wait_for_selector(page, 'div[data-testid="primaryColumn"]', timeout=30000, description="login verification"):
                    print("Login session expired. Please run login_manual.py again.")
                    return result
                
                print("Login verified successfully")
                
                # Use single page for tweets and retweets
                main_page = await context.new_page()
                main_page.set_default_timeout(30000)
                
                # Get basic profile info
                try:
                    result["user_profile"] = await scrape_user_profile(main_page, username)
                except Exception as e:
                    print(f"Error scraping profile: {str(e)}")
                
                # Get tweets
                try:
                    tweets = await scrape_tweets(main_page, username)
                    if tweets:  # Only update if we got some tweets
                        result["tweets"] = tweets
                    print(f"Successfully scraped {len(tweets)} tweets")
                except Exception as e:
                    print(f"Error scraping tweets: {str(e)}")
                
                # Get retweets
                try:
                    retweets = await scrape_retweets(main_page, username)
                    if retweets:  # Only update if we got some retweets
                        result["retweets"] = retweets
                    print(f"Successfully scraped {len(retweets)} retweets")
                except Exception as e:
                    print(f"Error scraping retweets: {str(e)}")
                
                await main_page.close()
                
            except Exception as e:
                print(f"Error during scraping: {str(e)}")
            finally:
                try:
                    await browser.close()
                except:
                    pass
                    
    except Exception as e:
        print(f"Critical error: {str(e)}")
    
    return result
