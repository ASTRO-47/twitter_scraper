import os
import json
import asyncio
import random
import hashlib
import time
import glob
from typing import List, Dict, Optional, Tuple, Set
from playwright.async_api import async_playwright, TimeoutError, Page
from pathlib import Path

# Configuration
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Use relative path for cookies file
COOKIES_FILE = os.path.join(os.path.dirname(__file__), 'twitter_cookies.json')

# Rate limiting configuration
SCROLL_DELAY = 1  # seconds between scrolls  
REQUEST_DELAY = 0.5  # seconds between requests
MAX_RETRIES = 2
TIMEOUT = 3000  # 3 seconds

async def safe_wait_for_selector(page: Page, selector: str, timeout: int = TIMEOUT, description: str = "element") -> bool:
    """Safely wait for a selector with proper error handling."""
    try:
        await page.wait_for_selector(selector, timeout=timeout, state="attached")
        return True
    except TimeoutError:
        print(f"Timeout waiting for {description} (selector: {selector})")
        return False
    except Exception as e:
        print(f"Error waiting for {description}: {str(e)}")
        return False

async def safe_screenshot(element, path: str, description: str = "element") -> str:
    """Safely take a screenshot with error handling."""
    try:
        await element.screenshot(path=path)
        return path
    except Exception as e:
        print(f"Could not take screenshot for {description}: {str(e)}")
        return ""

async def rate_limit_delay(delay: float = REQUEST_DELAY) -> None:
    """Add delay for rate limiting."""
    await asyncio.sleep(delay)

def generate_secure_tweet_id(tweet_element_html: str, fallback_content: str = "") -> str:
    """Generate a secure, unique tweet ID using hashing."""
    content = tweet_element_html + fallback_content + str(time.time())
    return hashlib.md5(content.encode()).hexdigest()[:16]

def clean_username_for_filename(username: str) -> str:
    """Clean username to be filesystem-safe."""
    # Remove @ symbol and any other problematic characters
    cleaned = username.replace('@', '').replace(' ', '_').replace('/', '_').replace('\\', '_')
    # Remove any other special characters that might cause issues
    cleaned = ''.join(c for c in cleaned if c.isalnum() or c in '_-')
    return cleaned

def cleanup_existing_screenshots(username: str) -> None:
    """Remove existing screenshots for a user to prevent duplicates."""
    cleaned_username = clean_username_for_filename(username)
    
    # List of possible naming patterns to clean up
    patterns = [
        f"{cleaned_username}_tweet_*.png",
        f"{cleaned_username}_retweet_*.png",
        f"@{cleaned_username}_tweet_*.png",
        f"@{cleaned_username}_retweet_*.png",
        f"@{cleaned_username} _tweet_*.png",
        f"@{cleaned_username} _retweet_*.png",
        f"{username}_tweet_*.png",
        f"{username}_retweet_*.png",
        f"@{username}_tweet_*.png",
        f"@{username}_retweet_*.png",
        f"@{username} _tweet_*.png",
        f"@{username} _retweet_*.png",
    ]
    
    removed_count = 0
    for pattern in patterns:
        files = glob.glob(os.path.join(SCREENSHOTS_DIR, pattern))
        for file_path in files:
            try:
                os.remove(file_path)
                removed_count += 1
            except Exception as e:
                print(f"Warning: Could not remove {file_path}: {e}")
    
    if removed_count > 0:
        print(f"Cleaned up {removed_count} existing screenshots for user {username}")

def generate_unique_screenshot_filename(username: str, content_type: str, index: int) -> str:
    """Generate a unique screenshot filename with timestamp to avoid conflicts."""
    cleaned_username = clean_username_for_filename(username)
    timestamp = int(time.time())
    return f"{cleaned_username}_{content_type}_{index}_{timestamp}.png"

async def wait_for_profile_load(page: Page, username: str) -> bool:
    """Wait for profile to load with multiple fallback strategies."""
    try:
        # Strategy 1: Wait for tweets
        if await safe_wait_for_selector(page, 'article[data-testid="tweet"]', timeout=3000, description="tweets"):
            return True
        
        # Strategy 2: Wait for empty state
        if await safe_wait_for_selector(page, 'div[data-testid="emptyState"]', timeout=2000, description="empty state"):
            print(f"Profile {username} has no tweets or is empty")
            return True
            
        # Strategy 3: Check if profile header exists (private or protected account)
        if await safe_wait_for_selector(page, 'div[data-testid="UserName"]', timeout=3000, description="profile header"):
            print(f"Profile {username} loaded but may be private")
            return True
            
        print(f"Timeout waiting for profile {username} to load")
        return False
    except Exception as e:
        print(f"Error waiting for profile load: {str(e)}")
        return False

async def scrape_user_profile(page: Page, username: str) -> Dict[str, str]:
    """Scrape user profile information with improved error handling."""
    try:
        print(f"Navigating to profile page for @{username}...")
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=TIMEOUT)
        await rate_limit_delay()
        
        if not await safe_wait_for_selector(page, 'div[data-testid="UserName"]', description="profile"):
            print(f"Could not load profile for @{username}")
            return {"username": username, "bio": ""}
        
        # Get display name with multiple selector fallbacks
        display_name = ""
        name_selectors = [
            'div[data-testid="UserName"] span',
            'div[data-testid="UserName"] div span',
            'h1[data-testid="UserName"] span'
        ]
        
        for selector in name_selectors:
            try:
                name_element = page.locator(selector).first
                if await name_element.count() > 0:
                    display_name = await name_element.inner_text()
                    if display_name:
                        break
            except Exception as e:
                print(f"Error with name selector {selector}: {str(e)}")
                continue
        
        # Get bio with retry and multiple selectors
        bio = ""
        bio_selectors = [
            'div[data-testid="UserDescription"]',
            'div[data-testid="UserBio"]',
            'div[data-testid="UserProfessionalCategory"]'
        ]
        
        for attempt in range(MAX_RETRIES):
            for selector in bio_selectors:
                try:
                    bio_element = page.locator(selector)
                    if await bio_element.count() > 0:
                        bio = await bio_element.inner_text()
                        if bio:
                            break
                except Exception as e:
                    print(f"Error with bio selector {selector}: {str(e)}")
                    continue
            
            if bio:
                break
            await rate_limit_delay()
        
        return {
            "username": display_name or username,
            "bio": bio.strip() if bio else ""
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
    """Get the main tweet content with improved selector robustness."""
    content_selectors = [
        'div[data-testid="tweetText"]',
        'div[lang]:not([data-testid])',
        'article div[lang]',
        'div[role="article"] div[lang]',
        'div[dir="auto"]:not([data-testid])',
        'span[lang]'
    ]
    
    for selector in content_selectors:
        try:
            elements = tweet_element.locator(selector)
            count = await elements.count()
            if count > 0:
                texts = []
                for i in range(min(count, 5)):  # Limit to avoid memory issues
                    try:
                        text = await elements.nth(i).inner_text()
                        if text and len(text.strip()) > 0:
                            texts.append(text.strip())
                    except Exception:
                        continue
                
                if texts:
                    return " ".join(texts)
        except Exception:
            continue
    
    # Final fallback
    try:
        text = await tweet_element.inner_text()
        if text and len(text.strip()) > 10:  # Avoid getting just metadata
            return text.strip()[:500]  # Limit length
    except Exception:
        pass
    
    return ""

async def get_tweet_date(tweet_element) -> str:
    """Extract the date/time when the tweet was posted."""
    try:
        # Method 1: Try to get datetime from time element
        time_element = tweet_element.locator('time').first
        if await time_element.count() > 0:
            datetime_attr = await time_element.get_attribute('datetime')
            if datetime_attr:
                return datetime_attr
    except Exception:
        pass
    
    # Method 2: Try to get from title attribute of time element
    try:
        time_element = tweet_element.locator('time').first
        if await time_element.count() > 0:
            title_attr = await time_element.get_attribute('title')
            if title_attr:
                return title_attr
    except Exception:
        pass
    
    # Method 3: Try to get text content from time element
    try:
        time_element = tweet_element.locator('time').first
        if await time_element.count() > 0:
            time_text = await time_element.inner_text()
            if time_text:
                return time_text.strip()
    except Exception:
        pass
    
    # Method 4: Look for any timestamp in the tweet
    try:
        # Look for common date/time patterns in the tweet
        timestamp_selectors = [
            'a[href*="/status/"] time',
            'time[datetime]',
            '[data-testid*="time"]',
            '[aria-label*="time"]',
            '[title*="AM"]',
            '[title*="PM"]'
        ]
        
        for selector in timestamp_selectors:
            try:
                element = tweet_element.locator(selector).first
                if await element.count() > 0:
                    # Try datetime attribute first
                    datetime_attr = await element.get_attribute('datetime')
                    if datetime_attr:
                        return datetime_attr
                    
                    # Try title attribute
                    title_attr = await element.get_attribute('title')
                    if title_attr:
                        return title_attr
                    
                    # Try text content
                    text = await element.inner_text()
                    if text:
                        return text.strip()
            except Exception:
                continue
    except Exception:
        pass
    
    return ""

async def get_tweet_id(tweet_element) -> str:
    """Get a unique identifier for a tweet with improved robustness."""
    # Method 1: Try to get tweet status ID from URL
    try:
        links = tweet_element.locator('a[href*="/status/"]')
        count = await links.count()
        for i in range(count):
            try:
                href = await links.nth(i).get_attribute('href')
                if href and "/status/" in href:
                    tweet_id = href.split('/status/')[-1].split('?')[0]
                    if tweet_id.isdigit() and len(tweet_id) > 10:
                        return tweet_id
            except Exception:
                continue
    except Exception:
        pass
    
    # Method 2: Try to get datetime from time element
    try:
        time_element = tweet_element.locator('time').first
        if await time_element.count() > 0:
            datetime_attr = await time_element.get_attribute('datetime')
            if datetime_attr:
                return f"time_{datetime_attr}"
    except Exception:
        pass
    
    # Method 3: Try to get data attributes
    try:
        data_attrs = ['data-tweet-id', 'data-testid', 'data-item-id']
        for attr in data_attrs:
            value = await tweet_element.get_attribute(attr)
            if value:
                return f"{attr}_{value}"
    except Exception:
        pass
    
    # Method 4: Generate from content hash
    try:
        # Get a small portion of HTML for hashing (avoid memory issues)
        html_snippet = await tweet_element.inner_html()
        if html_snippet:
            # Take first 1000 chars to avoid memory issues
            content_hash = hashlib.md5(html_snippet[:1000].encode()).hexdigest()
            return f"hash_{content_hash}"
    except Exception:
        pass
    
    # Method 5: Last resort - timestamp with random
    return f"fallback_{int(time.time())}_{random.randint(1000, 9999)}"

async def is_repost(tweet_element) -> bool:
    """Check if tweet is a repost (retweet without comment) with improved detection."""
    try:
        # Method 1: Check for retweet indicator in social context
        social_selectors = [
            'div[data-testid="socialContext"]',
            'div[data-testid="tweet"] div[data-testid="socialContext"]'
        ]
        
        for selector in social_selectors:
            try:
                social_context = tweet_element.locator(selector)
                if await social_context.count() > 0:
                    social_text = await social_context.inner_text()
                    retweet_indicators = ["reposted", "retweeted", "retweet", "shared"]
                    if any(indicator in social_text.lower() for indicator in retweet_indicators):
                        print(f"Found retweet via social context: {social_text}")
                        return True
            except Exception:
                continue

        # Method 2: Check for retweet icon/action
        retweet_indicators = [
            'div[data-testid="retweetIcon"]',
            'div[data-testid="retweet"]',
            'div[aria-label*="retweet" i]',
            'div[aria-label*="repost" i]',
            'svg[data-testid="icon-retweet"]'
        ]
        
        for indicator in retweet_indicators:
            try:
                element = tweet_element.locator(indicator)
                if await element.count() > 0:
                    print(f"Found retweet via indicator: {indicator}")
                    return True
            except Exception:
                continue

        # Method 3: Check for retweet text patterns
        try:
            article_text = await tweet_element.inner_text()
            if article_text:
                retweet_phrases = [
                    "retweeted", "reposted", "retweet", "shared this",
                    "reposted this", "retweeted this", "shared a"
                ]
                for phrase in retweet_phrases:
                    if phrase in article_text.lower():
                        print(f"Found retweet via text pattern: {phrase}")
                        return True
        except Exception:
            pass

        # Method 4: Check for nested tweet structure
        try:
            # Look for quoted or nested tweets
            nested_selectors = [
                'div[data-testid="tweet"] div[data-testid="tweet"]',
                'article div[data-testid="tweet"]'
            ]
            
            for selector in nested_selectors:
                nested_tweet = tweet_element.locator(selector)
                if await nested_tweet.count() > 0:
                    print("Found retweet via nested structure")
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
    """Get information about a retweet with improved extraction."""
    try:
        # Get the original tweet content
        main_content = await get_main_tweet_content(tweet_element)
        
        # Get username of original tweet author
        username = ""
        username_selectors = [
            'div[data-testid="User-Name"] a',
            'div[data-testid="User-Name"] span:has-text("@")',
            'a[href*="/"]:not([href*="/status/"])'
        ]
        
        for selector in username_selectors:
            try:
                elements = tweet_element.locator(selector)
                count = await elements.count()
                for i in range(count):
                    element = elements.nth(i)
                    
                    # Try to get username from href
                    href = await element.get_attribute('href')
                    if href and '/' in href and not '/status/' in href:
                        potential_username = href.strip('/').split('/')[-1]
                        if potential_username and not potential_username.startswith('http'):
                            username = potential_username
                            break
                    
                    # Try to get username from text content
                    text = await element.inner_text()
                    if text and '@' in text:
                        username = text.strip('@').split()[0]
                        break
                        
                if username:
                    break
            except Exception:
                continue

        # Get bio with improved selectors for retweet context
        bio = ""
        bio_selectors = [
            'div[data-testid="UserDescription"]',
            'div[data-testid="UserBio"]',
            'div[data-testid="UserProfessionalCategory"]',
            'div[dir="ltr"][data-testid]:not([data-testid="tweetText"])',
            'div[dir="auto"]:has-text("·"):not([data-testid="tweetText"])',
            'div:has(> span):not([data-testid="tweetText"]):not([data-testid="User-Name"])',
        ]
        
        for selector in bio_selectors:
            try:
                bio_element = tweet_element.locator(selector)
                if await bio_element.count() > 0:
                    potential_bio = await bio_element.inner_text()
                    # Filter out non-bio content
                    if (potential_bio and 
                        len(potential_bio.strip()) > 0 and 
                        not potential_bio.strip().startswith('@') and
                        'reposted' not in potential_bio.lower() and
                        'retweeted' not in potential_bio.lower() and
                        len(potential_bio.strip()) > 5):
                        bio = potential_bio.strip()
                        break
            except Exception:
                continue

        return {
            "retweet_content": "",  # Pure retweets have no additional content
            "retweet_username": username,
            "retweet_profile_bio": bio,
            "retweet_main_content": main_content
        }

    except Exception as e:
        print(f"Could not get retweet info: {str(e)}")
        return None

async def scrape_tweets(page: Page, username: str, max_tweets: int = 100, max_retweets: int = 100) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Scrape tweets and retweets with improved efficiency and error handling."""
    tweets = []
    retweets = []
    processed_ids: Set[str] = set()
    
    try:
        print(f"\nStarting to scrape tweets for user: {username} (max {max_tweets} tweets, {max_retweets} retweets)")
        
        # Clean up existing screenshots to prevent duplicates
        cleanup_existing_screenshots(username)
        
        # Navigate to profile
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=TIMEOUT)
        
        if not await wait_for_profile_load(page, username):
            print("Profile could not be loaded")
            return tweets, retweets

        print("Profile loaded successfully")
        
        # Scrolling variables
        last_height = await page.evaluate("document.body.scrollHeight")
        no_new_items_count = 0
        max_no_new_items = 2  # Reduced from 3 to 2
        scroll_attempts = 0
        max_scroll_attempts = 10  # Reduced from 50 to 10

        while scroll_attempts < max_scroll_attempts:
            scroll_attempts += 1
            
            # Check if we've reached both limits early
            if len(tweets) >= max_tweets and len(retweets) >= max_retweets:
                print(f"Both limits reached: {len(tweets)} tweets, {len(retweets)} retweets. Stopping.")
                break
                
            try:
                # Wait for content to load
                await rate_limit_delay(SCROLL_DELAY)
                
                # Get all visible tweets
                tweet_elements = await page.locator('article[data-testid="tweet"]').all()
                print(f"[DEBUG] Found {len(tweet_elements)} tweet elements on scroll {scroll_attempts}")
                
                if not tweet_elements:
                    print("No tweets found on page")
                    break

                initial_count = len(tweets) + len(retweets)
                processed_in_batch = 0

                for idx, tweet in enumerate(tweet_elements):
                    try:
                        # Get unique tweet ID
                        tweet_id = await get_tweet_id(tweet)
                        
                        if tweet_id in processed_ids:
                            continue
                        
                        processed_ids.add(tweet_id)
                        processed_in_batch += 1
                        
                        # Check if it's a retweet
                        is_retweet = await is_repost(tweet)
                        
                        if is_retweet:
                            # Check retweet limit
                            if len(retweets) >= max_retweets:
                                print(f"Reached maximum retweets limit ({max_retweets}), skipping further retweets")
                                continue
                                
                            print(f"Processing retweet #{len(retweets)+1} (ID: {tweet_id})")
                            
                            # Get retweet date
                            retweet_date = await get_tweet_date(tweet)
                            
                            # Take screenshot with unique filename
                            screenshot_filename = generate_unique_screenshot_filename(username, "retweet", len(retweets)+1)
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
                            screenshot_path = await safe_screenshot(tweet, screenshot_path, "retweet")

                            # Get retweet info
                            retweet_info = await get_retweet_info(tweet)
                            if retweet_info:
                                retweet_info["retweet_date"] = retweet_date
                                retweet_info["retweet_screenshot"] = screenshot_path
                                retweets.append(retweet_info)
                                print(f"Successfully added retweet {len(retweets)} with date: {retweet_date}")
                            continue

                        # Check tweet limit
                        if len(tweets) >= max_tweets:
                            print(f"Reached maximum tweets limit ({max_tweets}), skipping further tweets")
                            continue

                        # Process as regular tweet
                        print(f"Processing tweet #{len(tweets)+1} (ID: {tweet_id})")
                        content = await get_main_tweet_content(tweet)
                        
                        if content:
                            # Get tweet date
                            tweet_date = await get_tweet_date(tweet)
                            
                            # Take screenshot with unique filename
                            screenshot_filename = generate_unique_screenshot_filename(username, "tweet", len(tweets)+1)
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
                            screenshot_path = await safe_screenshot(tweet, screenshot_path, "tweet")

                            tweet_data = {
                                "tweet_content": content,
                                "tweet_date": tweet_date,
                                "tweet_screenshot": screenshot_path
                            }

                            # Check for quoted tweet
                            quoted_info = await get_quoted_tweet_info(tweet)
                            if quoted_info:
                                tweet_data.update(quoted_info)

                            tweets.append(tweet_data)
                            print(f"Successfully added tweet {len(tweets)} with date: {tweet_date}")
                        else:
                            # Handle tweets without detectable content
                            print(f"Tweet {tweet_id} has no detectable content, skipping")

                    except Exception as e:
                        print(f"Error processing tweet element: {str(e)}")
                        continue

                # Check progress
                current_count = len(tweets) + len(retweets)
                print(f"Batch {scroll_attempts}: Processed {processed_in_batch} new items. Total: {len(tweets)} tweets, {len(retweets)} retweets")
                
                # Check if we've reached both limits
                if len(tweets) >= max_tweets and len(retweets) >= max_retweets:
                    print(f"Reached both limits: {len(tweets)} tweets (max: {max_tweets}), {len(retweets)} retweets (max: {max_retweets})")
                    break
                
                if current_count == initial_count:
                    no_new_items_count += 1
                    print(f"No new items found (attempt {no_new_items_count}/{max_no_new_items})")
                else:
                    no_new_items_count = 0

                if no_new_items_count >= max_no_new_items:
                    print("Reached end of timeline (no new items)")
                    break

                # Scroll down
                print(f"Scrolling for more content... (attempt {scroll_attempts})")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await rate_limit_delay(SCROLL_DELAY)

                # Check if page height changed
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    no_new_items_count += 1
                    print("Page height unchanged, may have reached end")
                else:
                    last_height = new_height

            except Exception as e:
                print(f"Error during scroll {scroll_attempts}: {str(e)}")
                no_new_items_count += 1

            # Emergency break conditions
            if no_new_items_count >= max_no_new_items:
                print("Stopping due to no new items")
                break

    except Exception as e:
        print(f"Error scraping tweets: {str(e)}")

    print(f"\nScraping completed after {scroll_attempts} scroll attempts!")
    print(f"Final results: {len(tweets)} tweets and {len(retweets)} retweets")
    return tweets, retweets

async def scrape_likes(page, username: str) -> List[Dict]:
    # Commented out for now as it needs further investigation
    return []

async def scrape_social_users(page: Page, username: str, user_type: str, max_users: int = 300) -> List[Dict[str, str]]:
    """Generic function to scrape followers or following with improved efficiency."""
    users = []
    try:
        # Navigate to the appropriate page
        url = f"https://twitter.com/{username}/{user_type}"
        print(f"Navigating to {url} (max: {max_users} users)")
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
        await rate_limit_delay()

        # Wait for content to load
        if not await safe_wait_for_selector(page, 'div[data-testid="cellInnerDiv"]', timeout=3000, description=f"{user_type} cells"):
            print(f"No {user_type} cells found")
            return users

        # Initialize tracking variables
        processed_usernames: Set[str] = set()
        no_new_users_count = 0
        max_no_new_users = 2  # Reduced from 3 to 2
        scroll_attempts = 0
        max_scroll_attempts = 30

        while scroll_attempts < max_scroll_attempts:
            scroll_attempts += 1
            try:
                # Get all visible user cells
                cells = await page.locator('div[data-testid="cellInnerDiv"]').all()
                
                if not cells:
                    no_new_users_count += 1
                    if no_new_users_count >= max_no_new_users:
                        print(f"No more {user_type} cells found after multiple attempts")
                        break
                    await rate_limit_delay()
                    continue

                initial_count = len(users)
                processed_in_batch = 0

                for cell in cells:
                    try:
                        # Extract username
                        cell_username = await extract_username_from_cell(cell)
                        if not cell_username or cell_username in processed_usernames:
                            continue
                        
                        # Check if we've reached the user limit
                        if len(users) >= max_users:
                            print(f"Reached maximum {user_type} limit ({max_users}), stopping collection")
                            break
                            
                        processed_usernames.add(cell_username)
                        processed_in_batch += 1
                        
                        # Extract display name
                        display_name = await extract_display_name_from_cell(cell, cell_username)
                        
                        # Extract bio
                        bio = await extract_bio_from_cell(cell)
                        
                        # Create user data based on type
                        if user_type == "followers":
                            user_data = {
                                "follower_name": display_name or cell_username,
                                "follower_bio": bio
                            }
                        else:  # following
                            user_data = {
                                "following_name": display_name or cell_username,
                                "following_bio": bio
                            }
                        
                        users.append(user_data)
                        print(f"Added {user_type[:-1]} #{len(users)}: @{cell_username}" + (f" ({display_name})" if display_name else ""))
                        
                        if bio:
                            print(f"  Bio: {bio[:50]}..." if len(bio) > 50 else f"  Bio: {bio}")
                        
                    except Exception as e:
                        print(f"Error processing {user_type} cell: {str(e)}")
                        continue

                # Check progress and limits
                current_count = len(users)
                print(f"Batch {scroll_attempts}: Processed {processed_in_batch} new {user_type}. Total: {current_count}")
                
                # Check if we've reached the user limit
                if len(users) >= max_users:
                    print(f"Reached maximum {user_type} limit ({max_users}), stopping")
                    break
                
                if current_count == initial_count:
                    no_new_users_count += 1
                    print(f"No new {user_type} found (attempt {no_new_users_count}/{max_no_new_users})")
                else:
                    no_new_users_count = 0

                if no_new_users_count >= max_no_new_users:
                    print(f"Reached end of {user_type} list")
                    break

                # Scroll down
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await rate_limit_delay(SCROLL_DELAY)

            except Exception as e:
                print(f"Error during {user_type} scroll {scroll_attempts}: {str(e)}")
                no_new_users_count += 1

        print(f"Total {user_type} collected: {len(users)}")
        return users

    except Exception as e:
        print(f"Error scraping {user_type}: {str(e)}")
        return users

async def extract_username_from_cell(cell) -> str:
    """Extract username from a user cell."""
    username_selectors = [
        'a[role="link"][href*="/"]',
        'a[href*="/"]',
        'div[data-testid="User-Name"] a'
    ]
    
    for selector in username_selectors:
        try:
            links = cell.locator(selector)
            count = await links.count()
            for i in range(count):
                href = await links.nth(i).get_attribute('href')
                if href and '/' in href and not '/status/' in href:
                    potential_username = href.strip('/').split('/')[-1]
                    if potential_username and not potential_username.startswith('http'):
                        return potential_username
        except Exception:
            continue
    
    return ""

async def extract_display_name_from_cell(cell, username: str) -> str:
    """Extract display name from a user cell."""
    name_selectors = [
        'div[data-testid="User-Name"] div:first-child span span',
        'div[data-testid="User-Name"] div span',
        'div[data-testid="User-Name"] span'
    ]
    
    for selector in name_selectors:
        try:
            name_element = cell.locator(selector).first
            if await name_element.count() > 0:
                name = await name_element.inner_text()
                if name and name.strip() and not name.startswith('@'):
                    # Clean up name
                    name = name.strip().replace("·", "").strip()
                    if name != username:  # Don't return username as display name
                        return name
        except Exception:
            continue
    
    return ""

async def extract_bio_from_cell(cell) -> str:
    """Extract bio from a user cell."""
    bio_selectors = [
        'div[data-testid="UserDescription"]',
        'div[data-testid="UserBio"]',
        'div[data-testid="UserProfessionalCategory"]'
    ]
    
    for selector in bio_selectors:
        try:
            bio_element = cell.locator(selector)
            if await bio_element.count() > 0:
                bio = await bio_element.inner_text()
                if bio:
                    return bio.strip().replace("Follow", "").strip()
        except Exception:
            continue
    
    # Fallback: try to find any descriptive text
    try:
        text_elements = cell.locator('div[dir="auto"]')
        count = await text_elements.count()
        for i in range(count):
            text = await text_elements.nth(i).inner_text()
            if text and len(text) > 5 and not text.startswith('@') and 'Follow' not in text:
                return text.strip()
    except Exception:
        pass
    
    return ""

async def scrape_followers(page: Page, username: str, max_followers: int = 300) -> List[Dict[str, str]]:
    """Scrape followers using the generic social scraping function."""
    return await scrape_social_users(page, username, "followers", max_followers)

async def scrape_following(page: Page, username: str, max_following: int = 300) -> List[Dict[str, str]]:
    """Scrape following using the generic social scraping function."""
    return await scrape_social_users(page, username, "following", max_following)

async def scrape_retweets(page, username: str, max_retweets: int = 100) -> List[Dict]:
    retweets = []
    try:
        print(f"Starting to scrape retweets for {username} (max: {max_retweets})")
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
        max_no_new_retweets = 2  # Reduced from 3 to 2
        
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
                        
                        # Check if we've reached the retweet limit
                        if len(retweets) >= max_retweets:
                            print(f"Reached maximum retweets limit ({max_retweets}), stopping retweet collection")
                            break
                        
                        # Get retweet data
                        original_content = await get_main_tweet_content(tweet)
                        retweeted_username = ""
                        retweeted_bio = ""
                        
                        # Get retweet date
                        retweet_date = await get_tweet_date(tweet)
                        
                        # Get username of retweeted content
                        try:
                            name_element = tweet.locator('div[data-testid="User-Name"] a').first
                            if await name_element.count() > 0:
                                retweeted_username = await name_element.get_attribute('href')
                                if retweeted_username:
                                    retweeted_username = retweeted_username.replace('/', '')
                        except Exception as e:
                            print(f"Could not get username: {str(e)}")
                        
                        # Get screenshot with unique filename
                        screenshot_path = ""
                        try:
                            screenshot_filename = generate_unique_screenshot_filename(username, "retweet", len(retweets)+1)
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
                            await tweet.screenshot(path=screenshot_path)
                        except Exception as e:
                            print(f"Could not get screenshot: {str(e)}")
                        
                        if original_content or retweeted_username or screenshot_path:
                            retweets.append({
                                "retweet_content": "",  # Retweet itself has no content
                                "retweet_username": retweeted_username,
                                "retweet_profile_bio": retweeted_bio,
                                "retweet_date": retweet_date,
                                "retweet_screenshot": screenshot_path,
                                "retweet_main_content": original_content
                            })
                            print(f"Added retweet {len(retweets)} from {retweeted_username} with date: {retweet_date}")
                    
                    except Exception as e:
                        print(f"Error processing retweet: {str(e)}")
                        continue
                
                # Check if we found any new retweets or reached limit
                if len(retweets) >= max_retweets:
                    print(f"Reached maximum retweets limit ({max_retweets}), stopping")
                    break
                    
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
                    await asyncio.sleep(1)
                    
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

async def scrape_twitter(username: str, max_tweets: int = 40, max_retweets: int = 40, max_followers: int = 300, max_following: int = 300) -> Dict:
    result = {
        "user_profile": {"username": username, "bio": ""},
        "following": [],
        "followers": []
    }
    
    try:
        async with async_playwright() as p:
            # Detect if we have a display available
            has_display = os.environ.get('DISPLAY') is not None
            
            # Launch browser with appropriate settings
            launch_args = [
                '--disable-extensions',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu' if not has_display else '',
            ]
            # Remove empty strings
            launch_args = [arg for arg in launch_args if arg]
            
            print(f"🖥️  Display available: {has_display} (DISPLAY={os.environ.get('DISPLAY', 'None')})")
            print(f"🚀 Browser args: {launch_args}")
            
            browser = await p.chromium.launch(
                headless=not has_display,  # Headless if no display, headed if display available
                args=launch_args
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
                await asyncio.sleep(1)
                
                # Check for login state using multiple indicators
                print("Verifying login status...")
                try:
                    # Wait a bit longer for the page to load completely
                    await asyncio.sleep(1)
                    
                    login_verified = False
                    
                    # Method 1: Check for login button (should not be present if logged in)
                    try:
                        login_button = page.locator('a[href="/login"]')
                        if await login_button.count() > 0:
                            print("Not logged in (login button found). Please run login_manual.py again.")
                            await browser.close()
                            return result
                    except Exception as e:
                        print(f"Could not check for login button: {str(e)}")
                    
                    # Method 2: Check for sign up button (should not be present if logged in)
                    try:
                        signup_button = page.locator('a[href="/i/flow/signup"]')
                        if await signup_button.count() > 0:
                            print("Not logged in (signup button found). Please run login_manual.py again.")
                            await browser.close()
                            return result
                    except Exception as e:
                        print(f"Could not check for signup button: {str(e)}")
                    
                    # Method 3: Try to find home timeline
                    try:
                        timeline = page.locator('div[data-testid="primaryColumn"]')
                        if await timeline.count() > 0:
                            print("Login verified - timeline found")
                            login_verified = True
                    except Exception as e:
                        print(f"Could not check for timeline: {str(e)}")
                    
                    # Method 4: Check for profile link
                    if not login_verified:
                        try:
                            profile_link = page.locator('a[data-testid="AppTabBar_Profile_Link"]')
                            if await profile_link.count() > 0:
                                print("Login verified - profile link found")
                                login_verified = True
                        except Exception as e:
                            print(f"Could not check for profile link: {str(e)}")
                    
                    # Method 5: Check for any authenticated content
                    if not login_verified:
                        try:
                            # Look for any authenticated content
                            authenticated_selectors = [
                                'div[data-testid="SideNav_AccountSwitcher_Button"]',
                                'div[data-testid="AppTabBar_Home_Link"]',
                                'div[data-testid="AppTabBar_Explore_Link"]',
                                'div[data-testid="AppTabBar_Notifications_Link"]'
                            ]
                            
                            for selector in authenticated_selectors:
                                element = page.locator(selector)
                                if await element.count() > 0:
                                    print(f"Login verified - authenticated element found: {selector}")
                                    login_verified = True
                                    break
                        except Exception as e:
                            print(f"Could not check for authenticated elements: {str(e)}")
                    
                    # Method 6: Check page title or URL for authentication
                    if not login_verified:
                        try:
                            current_url = page.url
                            if "twitter.com/home" in current_url or "x.com/home" in current_url:
                                print("Login verified - on home page")
                                login_verified = True
                        except Exception as e:
                            print(f"Could not check URL: {str(e)}")
                    
                    if not login_verified:
                        print("Could not verify login status with any method.")
                        print("This might be due to Twitter's anti-bot measures or page loading issues.")
                        print("Attempting to continue anyway...")
                        # Don't return here, continue with scraping attempt
                    else:
                        print("Login verified successfully")

                except Exception as e:
                    print(f"Error during login verification: {str(e)}")
                    print("Attempting to continue anyway...")
                    # Don't return here, continue with scraping attempt

                # Navigate directly to user's profile
                print(f"\nNavigating to profile @{username}...")
                try:
                    await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
                    await asyncio.sleep(1)
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
                tweets, retweets = await scrape_tweets(page, username, max_tweets, max_retweets)
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
                followers = await scrape_followers(social_page, username, max_followers)
                if followers:
                    result["followers"] = followers
                    print(f"Found {len(followers)} followers")
                else:
                    print("No followers found or error occurred")
                
                # Small delay between operations
                await asyncio.sleep(1)
                
                # Get following
                print(f"\nFetching following for @{username}...")
                following = await scrape_following(social_page, username, max_following)
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
    
    # --- Save result as JSON file in scraped_profiles directory ---
    try:
        scraped_profiles_dir = os.path.join(os.path.dirname(__file__), '..', 'scraped_profiles')
        os.makedirs(scraped_profiles_dir, exist_ok=True)
        json_path = os.path.join(scraped_profiles_dir, f"{username}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Scraped profile saved to {json_path}")
    except Exception as e:
        print(f"Error saving scraped profile: {str(e)}")
    # --- End save ---
    
    return result

def manually_cleanup_screenshots(username: str) -> None:
    """Manually clean up screenshots for a specific user."""
    print(f"Manually cleaning up screenshots for user: {username}")
    cleanup_existing_screenshots(username)
    print("Cleanup completed.")

def cleanup_all_screenshots() -> None:
    """Clean up all screenshots in the screenshots directory."""
    try:
        files = glob.glob(os.path.join(SCREENSHOTS_DIR, "*.png"))
        removed_count = 0
        for file_path in files:
            try:
                os.remove(file_path)
                removed_count += 1
            except Exception as e:
                print(f"Warning: Could not remove {file_path}: {e}")
        print(f"Cleaned up {removed_count} total screenshots")
    except Exception as e:
        print(f"Error during cleanup: {e}")
