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
        print(f"Navigating to profile page for @{username}...")
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        
        if not await safe_wait_for_selector(page, 'div[data-testid="UserName"]', description="profile", timeout=10000):
            print(f"Could not load profile for @{username}")
            return {"username": username, "bio": ""}
        
        # Get display name
        display_name = ""
        try:
            name_element = page.locator('div[data-testid="UserName"] span').first
            if await name_element.count() > 0:
                display_name = await name_element.inner_text()
        except Exception as e:
            print(f"Error getting display name: {str(e)}")
        
        # Get bio with retry
        bio = ""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                bio_element = page.locator('div[data-testid="UserDescription"]')
                if await bio_element.count() > 0:
                    bio = await bio_element.inner_text()
                    if bio:
                        break
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error getting bio (attempt {attempt + 1}): {str(e)}")
                await asyncio.sleep(1)
            
        return {
            "username": display_name or username,
            "bio": bio
        }

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
    # Commented out for now as it needs further investigation
    return []

async def scrape_followers(page, username: str) -> List[Dict]:
    followers = []
    try:
        # Navigate to followers page
        await page.goto(f"https://twitter.com/{username}/followers")
        await asyncio.sleep(2)

        # Initialize scroll tracking
        last_height = await page.evaluate('document.body.scrollHeight')
        processed_usernames = set()
        previous_count = 0
        same_count_iterations = 0
        
        while True:  # Keep scrolling until we truly reach the end
            # Get all visible user cells
            cells = await page.query_selector_all('div[data-testid="cellInnerDiv"]')
            
            if not cells:
                if same_count_iterations >= 3:  # Try a few times before giving up
                    print("No more follower cells found after multiple attempts")
                    break
                same_count_iterations += 1
                await asyncio.sleep(2)  # Wait a bit longer
                continue
            
            # Process visible cells
            for cell in cells:
                try:
                    # Get username (look for the link containing the username)
                    username = ""
                    links = await cell.query_selector_all('a[role="link"]')
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and '/' in href:
                            potential_username = href.strip('/').split('/')[-1]
                            if potential_username and potential_username not in processed_usernames:
                                username = potential_username
                                break
                    
                    if not username or username in processed_usernames:
                        continue
                        
                    # Get display name - try multiple selectors
                    name = ""
                    try:
                        # Try primary name selector
                        name_element = await cell.query_selector('div[data-testid="User-Name"] div:first-child span span')
                        if name_element:
                            name = await name_element.inner_text()
                        
                        # If not found, try secondary selector
                        if not name:
                            name_element = await cell.query_selector('div[data-testid="User-Name"] div span')
                            if name_element:
                                name = await name_element.inner_text()
                                
                        # Clean up name
                        if name:
                            name = name.strip()
                            # Remove verified badge text if present
                            name = name.replace("·", "").strip()
                    except Exception as e:
                        print(f"Error getting name for @{username}: {str(e)}")
                        
                    # Get bio - try multiple approaches
                    bio = ""
                    try:
                        # Try primary bio selector
                        bio_element = await cell.query_selector('div[data-testid="UserDescription"]')
                        if bio_element:
                            bio = await bio_element.inner_text()
                        
                        # If not found, try professional category
                        if not bio:
                            prof_element = await cell.query_selector('div[data-testid="UserProfessionalCategory"]')
                            if prof_element:
                                bio = await prof_element.inner_text()
                        
                        # If still not found, try generic text content
                        if not bio:
                            text_elements = await cell.query_selector_all('div[dir="auto"]')
                            for element in text_elements:
                                text = await element.inner_text()
                                if text and len(text) > 5 and not text.startswith('@') and 'Follow' not in text:
                                    bio = text
                                    break
                                    
                        # Clean up bio
                        if bio:
                            bio = bio.strip()
                            # Remove common unwanted text
                            bio = bio.replace("Follow", "").strip()
                    except Exception as e:
                        print(f"Error getting bio for @{username}: {str(e)}")
                        
                    # Add to followers list
                    followers.append({
                        "follower_name": name or username,  # Use username as fallback if no display name
                        "follower_bio": bio or ""
                    })
                    processed_usernames.add(username)
                    print(f"Added follower: @{username}" + (f" ({name})" if name else ""))
                    if bio:
                        print(f"Bio: {bio[:50]}..." if len(bio) > 50 else f"Bio: {bio}")
                    
                except Exception as e:
                    print(f"Error processing follower cell: {str(e)}")
                    continue
            
            # Check if we're still finding new followers
            current_count = len(followers)
            if current_count == previous_count:
                same_count_iterations += 1
            else:
                same_count_iterations = 0
                previous_count = current_count
            
            # Only stop if we've gone several iterations without finding new followers
            if same_count_iterations >= 3:
                # Try one final aggressive scroll
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight + 1000)')
                await asyncio.sleep(2)
                
                # Check if this found any new content
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    print("Reached end of followers list")
                    break
                    
                last_height = new_height
                same_count_iterations = 0
                continue
            
            # Scroll down
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)  # Increased wait time to ensure content loads
            
            # Print progress
            print(f"Collected {len(followers)} followers so far...")

    except Exception as e:
        print(f"Error in followers scraping: {str(e)}")
        
    print(f"Total followers collected: {len(followers)}")
    return followers

async def scrape_following(page, username: str) -> List[Dict]:
    following = []
    try:
        # Navigate to following page
        await page.goto(f"https://twitter.com/{username}/following")
        await asyncio.sleep(2)

        # Initialize scroll tracking
        last_height = await page.evaluate('document.body.scrollHeight')
        processed_usernames = set()
        previous_count = 0
        same_count_iterations = 0
        
        while True:  # Keep scrolling until we truly reach the end
            # Get all visible user cells
            cells = await page.query_selector_all('div[data-testid="cellInnerDiv"]')
            
            if not cells:
                if same_count_iterations >= 3:  # Try a few times before giving up
                    print("No more following cells found after multiple attempts")
                    break
                same_count_iterations += 1
                await asyncio.sleep(2)  # Wait a bit longer
                continue
            
            # Process visible cells
            for cell in cells:
                try:
                    # Get username (look for the link containing the username)
                    username = ""
                    links = await cell.query_selector_all('a[role="link"]')
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and '/' in href:
                            potential_username = href.strip('/').split('/')[-1]
                            if potential_username and potential_username not in processed_usernames:
                                username = potential_username
                                break
                    
                    if not username or username in processed_usernames:
                        continue
                        
                    # Get display name - try multiple selectors
                    name = ""
                    try:
                        # Try primary name selector
                        name_element = await cell.query_selector('div[data-testid="User-Name"] div:first-child span span')
                        if name_element:
                            name = await name_element.inner_text()
                        
                        # If not found, try secondary selector
                        if not name:
                            name_element = await cell.query_selector('div[data-testid="User-Name"] div span')
                            if name_element:
                                name = await name_element.inner_text()
                                
                        # Clean up name
                        if name:
                            name = name.strip()
                            # Remove verified badge text if present
                            name = name.replace("·", "").strip()
                    except Exception as e:
                        print(f"Error getting name for @{username}: {str(e)}")
                        
                    # Get bio - try multiple approaches
                    bio = ""
                    try:
                        # Try primary bio selector
                        bio_element = await cell.query_selector('div[data-testid="UserDescription"]')
                        if bio_element:
                            bio = await bio_element.inner_text()
                        
                        # If not found, try professional category
                        if not bio:
                            prof_element = await cell.query_selector('div[data-testid="UserProfessionalCategory"]')
                            if prof_element:
                                bio = await prof_element.inner_text()
                        
                        # If still not found, try generic text content
                        if not bio:
                            text_elements = await cell.query_selector_all('div[dir="auto"]')
                            for element in text_elements:
                                text = await element.inner_text()
                                if text and len(text) > 5 and not text.startswith('@') and 'Follow' not in text:
                                    bio = text
                                    break
                                    
                        # Clean up bio
                        if bio:
                            bio = bio.strip()
                            # Remove common unwanted text
                            bio = bio.replace("Follow", "").strip()
                    except Exception as e:
                        print(f"Error getting bio for @{username}: {str(e)}")
                        
                    # Add to following list
                    following.append({
                        "following_name": name or username,  # Use username as fallback if no display name
                        "following_bio": bio or ""
                    })
                    processed_usernames.add(username)
                    print(f"Added following: @{username}" + (f" ({name})" if name else ""))
                    if bio:
                        print(f"Bio: {bio[:50]}..." if len(bio) > 50 else f"Bio: {bio}")
                    
                except Exception as e:
                    print(f"Error processing following cell: {str(e)}")
                    continue
            
            # Check if we're still finding new following
            current_count = len(following)
            if current_count == previous_count:
                same_count_iterations += 1
            else:
                same_count_iterations = 0
                previous_count = current_count
            
            # Only stop if we've gone several iterations without finding new following
            if same_count_iterations >= 3:
                # Try one final aggressive scroll
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight + 1000)')
                await asyncio.sleep(2)
                
                # Check if this found any new content
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    print("Reached end of following list")
                    break
                    
                last_height = new_height
                same_count_iterations = 0
                continue
            
            # Scroll down
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)  # Increased wait time to ensure content loads
            
            # Print progress
            print(f"Collected {len(following)} following so far...")

    except Exception as e:
        print(f"Error in following scraping: {str(e)}")
        
    print(f"Total following collected: {len(following)}")
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
        "following": [],
        "followers": []
    }
    
    try:
        async with async_playwright() as p:
            # Launch browser in headless mode
            browser = await p.chromium.launch(
                headless=True,  # Run in headless mode
                args=['--disable-extensions']
            )
            
            # Create context with larger viewport and modern user agent
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            )
            
            # Load cookies
            if os.path.exists(COOKIES_FILE):
                try:
                    with open(COOKIES_FILE, "r") as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    print("Cookies loaded successfully")
                except Exception as e:
                    print(f"Error loading cookies: {str(e)}")
                    await browser.close()
                    return result
            else:
                print("No cookies file found. Please run login_manual.py first")
                await browser.close()
                return result
            
            try:
                # Create main page for profile info
                page = await context.new_page()
                page.set_default_timeout(30000)  # Set back to 30 seconds
                
                # First try to access Twitter directly
                print("\nAccessing Twitter...")
                try:
                    await page.goto("https://twitter.com", wait_until="domcontentloaded")
                except Exception as e:
                    print(f"Error accessing Twitter: {str(e)}")
                    await browser.close()
                    return result

                # Short wait for initial load
                await asyncio.sleep(2)
                
                # Check for login state using multiple indicators
                print("Verifying login status...")
                try:
                    # Check for login button
                    login_button = page.locator('a[href="/login"]')
                    if await login_button.count() > 0:
                        print("Not logged in (login button found). Please run login_manual.py again.")
                        await browser.close()
                        return result

                    # Check for sign up button
                    signup_button = page.locator('a[href="/i/flow/signup"]')
                    if await signup_button.count() > 0:
                        print("Not logged in (signup button found). Please run login_manual.py again.")
                        await browser.close()
                        return result

                    # Try to find home timeline
                    timeline = page.locator('div[data-testid="primaryColumn"]')
                    if not await timeline.count() > 0:
                        print("Could not verify login status. Please run login_manual.py again.")
                        await browser.close()
                        return result

                    print("Login verified successfully")

                except Exception as e:
                    print(f"Error during login verification: {str(e)}")
                    await browser.close()
                    return result

                # Navigate directly to user's profile
                print(f"\nNavigating to profile @{username}...")
                try:
                    await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                except Exception as e:
                    print(f"Error navigating to profile: {str(e)}")
                    await browser.close()
                    return result
                
                # Verify profile exists and is accessible
                try:
                    # Check for error messages
                    error_selectors = [
                        'div[data-testid="error-detail"]',
                        'div[data-testid="empty-state"]',
                        'div[data-testid="404-error"]'
                    ]
                    
                    for selector in error_selectors:
                        error_element = page.locator(selector)
                        if await error_element.count() > 0:
                            error_text = await error_element.inner_text()
                            print(f"Profile error: {error_text}")
                            await browser.close()
                            return result
                            
                    # Verify profile content is visible
                    profile_header = page.locator('div[data-testid="UserName"]')
                    if not await profile_header.count() > 0:
                        print(f"Could not access profile @{username}")
                        await browser.close()
                        return result
                        
                except Exception as e:
                    print(f"Error verifying profile: {str(e)}")
                    await browser.close()
                    return result

                # Get profile info
                print(f"Fetching profile info for @{username}...")
                result["user_profile"] = await scrape_user_profile(page, username)
                print(f"Profile info fetched: {result['user_profile']}")
                
                if not result["user_profile"]["bio"] and not result["user_profile"]["username"]:
                    print(f"Could not fetch profile info for @{username}")
                    await browser.close()
                    return result
                
                # Get tweets and retweets
                print(f"\nFetching tweets and retweets for @{username}...")
                tweets, retweets = await scrape_tweets(page, username)
                if tweets:
                    result["tweets"] = tweets
                    print(f"Found {len(tweets)} tweets")
                else:
                    print("No tweets found or error occurred")
                    
                if retweets:
                    result["retweets"] = retweets
                    print(f"Found {len(retweets)} retweets")
                else:
                    print("No retweets found or error occurred")
                
                # Create a new page for social data (followers/following)
                social_page = await context.new_page()
                social_page.set_default_timeout(30000)
                
                # Get followers first
                print(f"\nFetching followers for @{username}...")
                followers = await scrape_followers(social_page, username)
                if followers:
                    result["followers"] = followers
                    print(f"Found {len(followers)} followers")
                else:
                    print("No followers found or error occurred")
                
                # Small delay between operations
                await asyncio.sleep(2)
                
                # Get following
                print(f"\nFetching following for @{username}...")
                following = await scrape_following(social_page, username)
                if following:
                    result["following"] = following
                    print(f"Found {len(following)} following")
                else:
                    print("No following found or error occurred")
                
                await social_page.close()
                
                # Scraping completed
                print("\nScraping completed successfully!")
                
            except Exception as e:
                print(f"Error during scraping: {str(e)}")
            finally:
                print("\nClosing browser...")
                await browser.close()
                    
    except Exception as e:
        print(f"Critical error: {str(e)}")
    
    return result
