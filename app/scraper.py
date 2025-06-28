import os
import json
import asyncio
import random
from typing import List, Dict, Optional, Tuple
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
        except Exception:
            bio = ""
            
        return {"username": display_name, "bio": bio}
        
    except Exception as e:
        print(f"Error scraping profile: {str(e)}")
        return {"username": username, "bio": ""}

async def get_tweet_content(tweet_element) -> str:
    """Helper function to get tweet content from any tweet element"""
    try:
        content_element = tweet_element.locator('div[data-testid="tweetText"]').first
        if await content_element.count() > 0:
            return await content_element.inner_text()
    except Exception as e:
        print(f"Could not get tweet text: {str(e)}")
    return ""

async def get_quoted_tweet_info(tweet_element) -> Optional[Dict[str, str]]:
    """Get information about a quoted tweet if present"""
    try:
        quoted_container = tweet_element.locator('div:has(> div[data-testid="tweet"])').last
        if await quoted_container.count() > 0:
            quoted_text = await quoted_container.locator('div[data-testid="tweetText"]').inner_text()
            name_element = quoted_container.locator('div[data-testid="User-Name"] div span').first
            quoted_username = await name_element.inner_text() if await name_element.count() > 0 else ""
            return {
                "quoted_content": quoted_text,
                "quoted_username": quoted_username
            }
    except Exception as e:
        print(f"Could not get quoted tweet info: {str(e)}")
    return None

async def get_main_tweet_content(tweet_element) -> str:
    """Get the main tweet content, handling both regular and quoted tweets"""
    try:
        main_content_element = tweet_element.locator('div[data-testid="tweetText"]')
        if await main_content_element.count() > 0:
            return await main_content_element.inner_text()
    except Exception as e:
        print(f"Could not get main tweet content: {str(e)}")
    return ""

async def get_tweet_id(tweet_element) -> str:
    """Get a unique identifier for a tweet"""
    try:
        link = tweet_element.locator('a[href*="/status/"]').first
        if await link.count() > 0:
            href = await link.get_attribute('href')
            if href:
                return href.split('/status/')[-1].split('?')[0]
    except Exception:
        pass
    
    try:
        time = tweet_element.locator('time').first
        if await time.count() > 0:
            datetime = await time.get_attribute('datetime')
            if datetime:
                return datetime
    except Exception:
        pass
    
    try:
        html = await tweet_element.inner_html()
        return str(hash(html))
    except Exception:
        return str(random.randint(1, 1000000))

async def is_repost(tweet_element) -> bool:
    """Check if tweet is a repost (retweet without comment)"""
    try:
        # Method 1: Check for retweet indicator in the social context
        social_context = tweet_element.locator('div[data-testid="socialContext"]')
        if await social_context.count() > 0:
            social_text = await social_context.inner_text()
            if any(word.lower() in social_text.lower() for word in ["Reposted", "Retweeted"]):
                print("Found retweet via social context")
                return True

        # Method 2: Check for retweet icon/action
        retweet_indicators = [
            'div[data-testid="retweetIcon"]',
            'div[data-testid="retweet"]',
            'div[aria-label*="Retweet"]',
            'div[aria-label*="reposted"]'
        ]
        for indicator in retweet_indicators:
            element = tweet_element.locator(indicator)
            if await element.count() > 0:
                print(f"Found retweet via indicator: {indicator}")
                return True

        # Method 3: Check for retweet text in the article
        article_text = await tweet_element.inner_text()
        retweet_phrases = ["Retweeted", "Reposted", "Retweet", "reposted this", "retweeted this"]
        if any(phrase.lower() in article_text.lower() for phrase in retweet_phrases):
            print("Found retweet via article text")
            return True

        # Method 4: Check for specific retweet structure
        try:
            nested_tweet = tweet_element.locator('div[data-testid="tweet"] div[data-testid="tweet"]')
            if await nested_tweet.count() > 0:
                print("Found retweet via nested structure")
                return True
        except Exception:
            pass

        # Method 5: Check for retweet metadata
        try:
            time_element = tweet_element.locator('time')
            if await time_element.count() > 0:
                aria_label = await time_element.get_attribute('aria-label')
                if aria_label and any(word.lower() in aria_label.lower() for word in ["Retweeted", "Reposted"]):
                    print("Found retweet via time metadata")
                    return True
        except Exception:
            pass

    except Exception as e:
        print(f"Error checking repost status: {str(e)}")
    return False

async def is_quote_tweet(tweet_element) -> bool:
    """Check if tweet is a quote tweet"""
    try:
        quoted_tweet = tweet_element.locator('div[data-testid="tweet"]').last
        return await quoted_tweet.count() > 0
    except Exception:
        pass
    return False

async def get_retweet_info(tweet_element) -> Optional[Dict[str, str]]:
    """Get information about a retweet"""
    try:
        # Get the original tweet content
        main_content = ""
        try:
            content_selectors = [
                'div[data-testid="tweetText"]',
                'article div[lang]',
                'div[data-testid="tweet"] div[lang]',
                'div[data-testid="tweet"] div[data-testid="tweetText"]'
            ]
            
            for selector in content_selectors:
                content_element = tweet_element.locator(selector)
                if await content_element.count() > 0:
                    main_content = await content_element.inner_text()
                    if main_content:
                        break

            nested_tweet = tweet_element.locator('div[data-testid="tweet"] div[data-testid="tweetText"]')
            if await nested_tweet.count() > 0:
                main_content = await nested_tweet.inner_text()

        except Exception as e:
            print(f"Could not get retweet content: {str(e)}")

        # Get username of original tweet author
        username = ""
        try:
            name_element = tweet_element.locator('div[data-testid="User-Name"]')
            if await name_element.count() > 0:
                spans = name_element.locator('span')
                for i in range(await spans.count()):
                    span_text = await spans.nth(i).inner_text()
                    if '@' in span_text:
                        username = span_text.strip('@')
                        break
                
                if not username:
                    links = name_element.locator('a')
                    for i in range(await links.count()):
                        href = await links.nth(i).get_attribute('href')
                        if href and '/' in href:
                            username = href.strip('/').split('/')[-1]
                            break

        except Exception as e:
            print(f"Could not get retweeted username: {str(e)}")

        # Get bio
        bio = ""
        try:
            bio_element = tweet_element.locator('div[data-testid="UserDescription"]')
            if await bio_element.count() > 0:
                bio = await bio_element.inner_text()
        except Exception as e:
            print(f"Could not get bio: {str(e)}")

        return {
            "retweet_content": "",  # Pure retweets have no additional content
            "retweet_username": username,
            "retweet_profile_bio": bio,
            "retweet_main_content": main_content
        }

    except Exception as e:
        print(f"Could not get retweet info: {str(e)}")
        return None

async def scrape_tweets(page, username: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    tweets = []
    retweets = []
    processed_ids = set()  # Use tweet IDs instead of HTML hash
    
    try:
        print(f"\nStarting to scrape tweets for user: {username}")
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=30000)
        
        if not await wait_for_profile_load(page, username):
            print("Profile could not be loaded")
            return tweets, retweets

        print("Profile loaded successfully")
        last_height = await page.evaluate("document.body.scrollHeight")
        no_new_items_count = 0
        max_no_new_items = 3

        while True:
            try:
                # Wait for tweets to load
                await asyncio.sleep(2)
                
                # Get all visible tweets
                tweet_elements = await page.locator('article[data-testid="tweet"]').all()
                if not tweet_elements:
                    print("No tweets found on page")
                    break

                print(f"Found {len(tweet_elements)} tweet elements on current scroll")
                initial_count = len(tweets) + len(retweets)

                for tweet in tweet_elements:
                    try:
                        # Get unique tweet ID
                        tweet_id = await get_tweet_id(tweet)
                        
                        if tweet_id in processed_ids:
                            print("Skipping duplicate tweet")
                            continue
                            
                        processed_ids.add(tweet_id)
                        
                        # Check if it's a retweet
                        if await is_repost(tweet):
                            print(f"\nProcessing retweet (ID: {tweet_id})...")
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_retweet_{len(retweets)+1}.png")
                            try:
                                await tweet.screenshot(path=screenshot_path)
                            except Exception as e:
                                print(f"Could not get retweet screenshot: {str(e)}")
                                screenshot_path = ""

                            retweet_info = await get_retweet_info(tweet)
                            if retweet_info:
                                retweet_info["retweet_screenshot"] = screenshot_path
                                retweets.append(retweet_info)
                                print(f"Successfully added retweet {len(retweets)}")
                            continue

                        # Process as regular tweet
                        print(f"\nProcessing regular tweet (ID: {tweet_id})...")
                        content = await get_main_tweet_content(tweet)
                        
                        if not content:
                            print("Skipping empty tweet")
                            continue

                        screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_tweet_{len(tweets)+1}.png")
                        try:
                            await tweet.screenshot(path=screenshot_path)
                        except Exception as e:
                            print(f"Could not get tweet screenshot: {str(e)}")
                            screenshot_path = ""

                        tweet_data = {
                            "tweet_content": content,
                            "tweet_screenshot": screenshot_path
                        }

                        quoted_info = await get_quoted_tweet_info(tweet)
                        if quoted_info:
                            tweet_data.update(quoted_info)

                        tweets.append(tweet_data)
                        print(f"Successfully added tweet {len(tweets)}")

                    except Exception as e:
                        print(f"Error processing individual tweet/retweet: {str(e)}")
                        continue

                current_count = len(tweets) + len(retweets)
                print(f"\nCurrent progress: {len(tweets)} tweets and {len(retweets)} retweets")
                
                if current_count == initial_count:
                    no_new_items_count += 1
                    print(f"No new items found (attempt {no_new_items_count}/{max_no_new_items})")
                else:
                    no_new_items_count = 0

                if no_new_items_count >= max_no_new_items:
                    print("\nReached end of timeline")
                    break

                # Scroll down
                print("\nScrolling for more content...")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    no_new_items_count += 1
                else:
                    last_height = new_height

            except Exception as e:
                print(f"Error during scroll: {str(e)}")
                no_new_items_count += 1

            if no_new_items_count >= max_no_new_items:
                break

    except Exception as e:
        print(f"Error scraping tweets: {str(e)}")

    print(f"\nScraping completed!")
    print(f"Final results: {len(tweets)} tweets and {len(retweets)} retweets")
    return tweets, retweets

async def scrape_likes(page, username: str) -> List[Dict]:
    likes = []
    try:
        print(f"\nAccessing likes page for @{username}...")
        await page.goto(f"https://twitter.com/{username}/likes")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)  # Give more time for the page to load
        
        # Wait for either tweets or empty state
        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
        except TimeoutError:
            try:
                await page.wait_for_selector('div[data-testid="emptyState"]', timeout=5000)
                print("No likes found")
                return likes
            except TimeoutError:
                print("Could not load likes page")
                return likes

        # Get all visible liked tweets
        print("Scanning liked tweets...")
        liked_tweets = await page.locator('article[data-testid="tweet"]').all()
        
        for i, tweet in enumerate(liked_tweets, 1):
            try:
                print(f"Processing like {i}...")
                
                # Get tweet content
                content = ""
                try:
                    content_element = tweet.locator('div[data-testid="tweetText"]')
                    if await content_element.count() > 0:
                        content = await content_element.inner_text()
                except Exception as e:
                    print(f"Error getting like content: {str(e)}")

                # Get username
                username = ""
                try:
                    # Try multiple selectors for username
                    username_selectors = [
                        'div[data-testid="User-Name"] span span',
                        'div[data-testid="User-Name"] div[dir="ltr"] span',
                        'div[data-testid="User-Name"] a[role="link"] div span'
                    ]
                    
                    for selector in username_selectors:
                        name_element = tweet.locator(selector).first
                        if await name_element.count() > 0:
                            username = await name_element.inner_text()
                            if username:
                                break
                except Exception as e:
                    print(f"Error getting like username: {str(e)}")

                # Get bio
                bio = ""
                try:
                    bio_element = tweet.locator('div[data-testid="UserDescription"]')
                    if await bio_element.count() > 0:
                        bio = await bio_element.inner_text()
                except Exception as e:
                    print(f"Error getting like bio: {str(e)}")

                # Take screenshot
                screenshot_path = ""
                try:
                    screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_like_{i}.png")
                    await tweet.screenshot(path=screenshot_path)
                except Exception as e:
                    print(f"Error taking screenshot: {str(e)}")

                # Only add if we got some content
                if content or username:
                    likes.append({
                        "liked_tweet_content": content,
                        "liked_tweet_username": username,
                        "liked_tweet_profile_bio": bio,
                        "liked_tweet_screenshot": screenshot_path,
                        "liked_main_content": content
                    })
                    print(f"Successfully processed like {i}")

            except Exception as e:
                print(f"Error processing like {i}: {str(e)}")
                continue

            # Don't process too many at once
            if i >= 10:  # Limit to 10 likes for now
                break

        print(f"Found {len(likes)} likes")
        
    except Exception as e:
        print(f"Error scraping likes: {str(e)}")
    
    return likes

async def scrape_followers(page, username: str) -> List[Dict]:
    followers = []
    try:
        print(f"\nAccessing followers page for @{username}...")
        await page.goto(f"https://twitter.com/{username}/followers")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)  # Give more time for the page to load
        
        # Wait for either followers or empty state
        try:
            await page.wait_for_selector('div[data-testid="UserCell"]', timeout=15000)
        except TimeoutError:
            try:
                await page.wait_for_selector('div[data-testid="emptyState"]', timeout=5000)
                print("No followers found")
                return followers
            except TimeoutError:
                print("Could not load followers page")
                return followers

        # Get all visible followers
        print("Scanning followers...")
        follower_cells = await page.locator('div[data-testid="UserCell"]').all()
        
        for i, cell in enumerate(follower_cells, 1):
            try:
                print(f"Processing follower {i}...")
                
                # Get name
                name = ""
                try:
                    name_selectors = [
                        'div[data-testid="User-Name"] div:first-child span span',
                        'div[data-testid="User-Name"] div[dir="ltr"] span',
                        'div[data-testid="User-Name"] a[role="link"] div span'
                    ]
                    
                    for selector in name_selectors:
                        name_element = cell.locator(selector).first
                        if await name_element.count() > 0:
                            name = await name_element.inner_text()
                            if name:
                                break
                except Exception as e:
                    print(f"Error getting follower name: {str(e)}")

                # Get bio
                bio = ""
                try:
                    bio_element = cell.locator('div[data-testid="UserDescription"]')
                    if await bio_element.count() > 0:
                        bio = await bio_element.inner_text()
                except Exception as e:
                    print(f"Error getting follower bio: {str(e)}")

                # Only add if we got a name
                if name:
                    followers.append({
                        "follower_name": name,
                        "follower_bio": bio
                    })
                    print(f"Successfully processed follower {i}")

            except Exception as e:
                print(f"Error processing follower {i}: {str(e)}")
                continue

            # Don't process too many at once
            if i >= 10:  # Limit to 10 followers for now
                break

        print(f"Found {len(followers)} followers")
        
    except Exception as e:
        print(f"Error scraping followers: {str(e)}")
    
    return followers

async def scrape_following(page, username: str) -> List[Dict]:
    following = []
    try:
        print(f"\nAccessing following page for @{username}...")
        await page.goto(f"https://twitter.com/{username}/following")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)  # Give more time for the page to load
        
        # Wait for either following or empty state
        try:
            await page.wait_for_selector('div[data-testid="UserCell"]', timeout=15000)
        except TimeoutError:
            try:
                await page.wait_for_selector('div[data-testid="emptyState"]', timeout=5000)
                print("No following found")
                return following
            except TimeoutError:
                print("Could not load following page")
                return following

        # Get all visible following
        print("Scanning following...")
        following_cells = await page.locator('div[data-testid="UserCell"]').all()
        
        for i, cell in enumerate(following_cells, 1):
            try:
                print(f"Processing following {i}...")
                
                # Get name
                name = ""
                try:
                    name_selectors = [
                        'div[data-testid="User-Name"] div:first-child span span',
                        'div[data-testid="User-Name"] div[dir="ltr"] span',
                        'div[data-testid="User-Name"] a[role="link"] div span'
                    ]
                    
                    for selector in name_selectors:
                        name_element = cell.locator(selector).first
                        if await name_element.count() > 0:
                            name = await name_element.inner_text()
                            if name:
                                break
                except Exception as e:
                    print(f"Error getting following name: {str(e)}")

                # Get bio
                bio = ""
                try:
                    bio_element = cell.locator('div[data-testid="UserDescription"]')
                    if await bio_element.count() > 0:
                        bio = await bio_element.inner_text()
                except Exception as e:
                    print(f"Error getting following bio: {str(e)}")

                # Only add if we got a name
                if name:
                    following.append({
                        "following_name": name,
                        "following_bio": bio
                    })
                    print(f"Successfully processed following {i}")

            except Exception as e:
                print(f"Error processing following {i}: {str(e)}")
                continue

            # Don't process too many at once
            if i >= 10:  # Limit to 10 following for now
                break

        print(f"Found {len(following)} following")
        
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
                        
                        # Only process pure reposts (no comment)
                        if not await is_repost(tweet):
                            continue
                        
                        # Get retweet data
                        original_content = await get_main_tweet_content(tweet)
                        retweeted_username = ""
                        retweeted_bio = ""
                        
                        # Get username of retweeted content
                        try:
                            name_element = tweet.locator('div[data-testid="User-Name"] a').first
                            if await name_element.count() > 0:
                                retweeted_username = await name_element.get_attribute('href')
                                if retweeted_username:
                                    retweeted_username = retweeted_username.replace('/', '')
                        except Exception as e:
                            print(f"Could not get username: {str(e)}")
                        
                        # Get screenshot
                        screenshot_path = ""
                        try:
                            safe_username = retweeted_username.replace('@', '').replace('/', '_')
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_retweet_{len(retweets)+1}_{safe_username}.png")
                            await tweet.screenshot(path=screenshot_path)
                        except Exception as e:
                            print(f"Could not get screenshot: {str(e)}")
                        
                        if original_content or retweeted_username or screenshot_path:
                            retweets.append({
                                "retweet_content": "",  # Retweet itself has no content
                                "retweet_username": retweeted_username,
                                "retweet_profile_bio": retweeted_bio,
                                "retweet_screenshot": screenshot_path,
                                "retweet_main_content": original_content
                            })
                            print(f"Added retweet {len(retweets)} from {retweeted_username}")
                    
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
    result = {
        "user_profile": {"username": username, "bio": ""},
        "tweets": [],
        "retweets": [],
        "likes": [],
        "following": [],
        "followers": []
    }
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
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
            page.set_default_timeout(30000)
            
            try:
                # Verify login
                await page.goto("https://twitter.com/home", wait_until="load")
                await asyncio.sleep(2)
                
                if not await safe_wait_for_selector(page, 'div[data-testid="primaryColumn"]', timeout=30000, description="login verification"):
                    print("Login session expired. Please run login_manual.py again.")
                    return result
                
                print("Login verified successfully")
                
                # Get profile info
                print("\nScraping profile info...")
                result["user_profile"] = await scrape_user_profile(page, username)
                
                # Get tweets and retweets
                print("\nScraping tweets and retweets...")
                tweets, retweets = await scrape_tweets(page, username)
                if tweets:
                    result["tweets"] = tweets
                if retweets:
                    result["retweets"] = retweets
                print(f"Found {len(tweets)} tweets and {len(retweets)} retweets")
                
                # Get likes
                print("\nScraping likes...")
                likes = await scrape_likes(page, username)
                if likes:
                    result["likes"] = likes
                print(f"Found {len(likes)} likes")
                
                # Get following
                print("\nScraping following...")
                following = await scrape_following(page, username)
                if following:
                    result["following"] = following
                print(f"Found {len(following)} following")
                
                # Get followers
                print("\nScraping followers...")
                followers = await scrape_followers(page, username)
                if followers:
                    result["followers"] = followers
                print(f"Found {len(followers)} followers")
                
                print("\nScraping completed successfully!")
                
            except Exception as e:
                print(f"Error during scraping: {str(e)}")
            finally:
                await browser.close()
                    
    except Exception as e:
        print(f"Critical error: {str(e)}")
    
    return result
