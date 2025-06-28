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
        await page.wait_for_selector(selector, timeout=timeout, state="attached")
        return True
    except TimeoutError:
        print(f"Timeout waiting for {description}")
        return False
    except Exception as e:
        print(f"Error waiting for {description}: {str(e)}")
        return False

async def wait_for_profile_load(page, username: str) -> bool:
    try:
        # Wait for either tweets or empty state
        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
            return True
        except TimeoutError:
            try:
                await page.wait_for_selector('div[data-testid="emptyState"]', timeout=5000)
                print(f"Profile {username} not found or has no tweets")
                return False
            except TimeoutError:
                print(f"Timeout waiting for profile {username} to load")
                return False
    except Exception as e:
        print(f"Error waiting for profile load: {str(e)}")
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
        # Navigate to profile with better error handling
        try:
            await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=30000)
            if not await wait_for_profile_load(page, username):
                return tweets
                
        except Exception as e:
            print(f"Error accessing profile {username}: {str(e)}")
            return tweets
        
        last_height = await page.evaluate("document.body.scrollHeight")
        processed_tweets = set()
        no_new_tweets_count = 0
        max_no_new_tweets = 3
        
        while True:
            try:
                # Get all visible tweets with timeout
                tweet_elements = await page.locator('article[data-testid="tweet"]').all()
                if not tweet_elements:
                    print("No tweets found on page")
                    break
                    
                initial_tweet_count = len(tweets)
                
                for tweet in tweet_elements:
                    try:
                        # Get tweet ID or some unique identifier
                        tweet_html = await tweet.inner_html()
                        tweet_hash = hash(tweet_html)
                        
                        if tweet_hash in processed_tweets:
                            continue
                            
                        processed_tweets.add(tweet_hash)
                        
                        # Check if it's a retweet
                        retweet_indicator = tweet.locator('div[data-testid="socialContext"]')
                        if await retweet_indicator.count() > 0:
                            continue
                        
                        # Get tweet content
                        content = ""
                        try:
                            content_element = tweet.locator('div[data-testid="tweetText"]')
                            if await content_element.count() > 0:
                                content = await content_element.inner_text()
                        except Exception as e:
                            print(f"Could not get tweet text: {str(e)}")
                        
                        # Get screenshot
                        screenshot_path = ""
                        try:
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_tweet_{len(tweets)+1}.png")
                            await tweet.screenshot(path=screenshot_path)
                        except Exception as e:
                            print(f"Could not get screenshot: {str(e)}")
                        
                        if content or screenshot_path:
                            tweets.append({
                                "tweet_content": content,
                                "tweet_screenshot": screenshot_path
                            })
                            print(f"Added tweet {len(tweets)}")
                    
                    except Exception as e:
                        print(f"Error processing tweet: {str(e)}")
                        continue
                
                # Check if we found any new tweets
                if len(tweets) == initial_tweet_count:
                    no_new_tweets_count += 1
                else:
                    no_new_tweets_count = 0
                    print(f"Found {len(tweets)} tweets so far")
                
                # Stop if we haven't found new tweets in several scrolls
                if no_new_tweets_count >= max_no_new_tweets:
                    print("No new tweets found after multiple scrolls, stopping")
                    break
                
                # Scroll down with timeout
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    # Check if we've reached the bottom
                    new_height = await page.evaluate("document.body.scrollHeight")
                    if new_height == last_height:
                        no_new_tweets_count += 1
                    else:
                        last_height = new_height
                        
                except Exception as e:
                    print(f"Error scrolling: {str(e)}")
                    no_new_tweets_count += 1
                
            except Exception as e:
                print(f"Error during tweet collection: {str(e)}")
                no_new_tweets_count += 1
            
            # Emergency break if something goes wrong
            if no_new_tweets_count >= max_no_new_tweets:
                break
                
    except Exception as e:
        print(f"Error scraping tweets: {str(e)}")
    
    print(f"Total tweets scraped: {len(tweets)}")
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
        # Navigate to profile with better error handling
        try:
            await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=30000)
            if not await wait_for_profile_load(page, username):
                return retweets
                
        except Exception as e:
            print(f"Error accessing profile {username}: {str(e)}")
            return retweets
        
        last_height = await page.evaluate("document.body.scrollHeight")
        processed_retweets = set()
        no_new_retweets_count = 0
        max_no_new_retweets = 3
        
        while True:
            try:
                # Get all visible tweets with timeout
                tweet_elements = await page.locator('article[data-testid="tweet"]').all()
                if not tweet_elements:
                    print("No tweets found on page")
                    break
                    
                initial_retweet_count = len(retweets)
                
                for tweet in tweet_elements:
                    try:
                        # Get tweet ID or some unique identifier
                        tweet_html = await tweet.inner_html()
                        tweet_hash = hash(tweet_html)
                        
                        if tweet_hash in processed_retweets:
                            continue
                            
                        processed_retweets.add(tweet_hash)
                        
                        # Check if it's a retweet
                        retweet_indicator = tweet.locator('div[data-testid="socialContext"]')
                        if await retweet_indicator.count() == 0:
                            continue
                        
                        # Get retweet data
                        content = ""
                        username = ""
                        bio = ""
                        main_content = ""
                        
                        # Get retweet content with timeout
                        try:
                            content_element = tweet.locator('div[data-testid="tweetText"]')
                            if await content_element.count() > 0:
                                content = await content_element.inner_text()
                        except Exception as e:
                            print(f"Could not get retweet text: {str(e)}")
                        
                        # Get username with timeout
                        try:
                            name_element = tweet.locator('div[data-testid="User-Name"] span').first
                            if await name_element.count() > 0:
                                username = await name_element.inner_text()
                        except Exception as e:
                            print(f"Could not get username: {str(e)}")
                        
                        # Get screenshot
                        screenshot_path = ""
                        try:
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_retweet_{len(retweets)+1}.png")
                            await tweet.screenshot(path=screenshot_path)
                        except Exception as e:
                            print(f"Could not get screenshot: {str(e)}")
                        
                        # Get original tweet content with timeout
                        try:
                            main_content_element = tweet.locator('div[data-testid="tweetText"]').nth(1)
                            if await main_content_element.count() > 0:
                                main_content = await main_content_element.inner_text()
                            else:
                                main_content = content
                        except Exception as e:
                            print(f"Could not get original content: {str(e)}")
                            main_content = content
                        
                        if content or username or screenshot_path:
                            retweets.append({
                                "retweet_content": content,
                                "retweet_username": username,
                                "retweet_profile_bio": bio,
                                "retweet_screenshot": screenshot_path,
                                "retweet_main_content": main_content
                            })
                            print(f"Added retweet {len(retweets)}")
                    
                    except Exception as e:
                        print(f"Error processing retweet: {str(e)}")
                        continue
                
                # Check if we found any new retweets
                if len(retweets) == initial_retweet_count:
                    no_new_retweets_count += 1
                else:
                    no_new_retweets_count = 0
                    print(f"Found {len(retweets)} retweets so far")
                
                # Stop if we haven't found new retweets in several scrolls
                if no_new_retweets_count >= max_no_new_retweets:
                    print("No new retweets found after multiple scrolls, stopping")
                    break
                
                # Scroll down with timeout
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    # Check if we've reached the bottom
                    new_height = await page.evaluate("document.body.scrollHeight")
                    if new_height == last_height:
                        no_new_retweets_count += 1
                    else:
                        last_height = new_height
                        
                except Exception as e:
                    print(f"Error scrolling: {str(e)}")
                    no_new_retweets_count += 1
                
            except Exception as e:
                print(f"Error during retweet collection: {str(e)}")
                no_new_retweets_count += 1
            
            # Emergency break if something goes wrong
            if no_new_retweets_count >= max_no_new_retweets:
                break
                
    except Exception as e:
        print(f"Error scraping retweets: {str(e)}")
    
    print(f"Total retweets scraped: {len(retweets)}")
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
