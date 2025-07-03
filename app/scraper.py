import os
import json
import asyncio
import random
import hashlib
import time
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, TimeoutError

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "twitter_cookies.json")

# Configuration for scraping limits and performance
MAX_TWEETS_PER_PROFILE = 100  # Limit to prevent infinite scraping
MAX_FOLLOWERS = 500  # Limit followers scraping
MAX_FOLLOWING = 500  # Limit following scraping
SCROLL_PAUSE_TIME = 3  # Increased wait time between scrolls
SCREENSHOT_TIMEOUT = 10000  # Timeout for screenshot operations

async def safe_wait_for_selector(page, selector, timeout=15000, description="element"):
    """Enhanced wait function with better error handling"""
    try:
        await page.wait_for_selector(selector, timeout=timeout, state="visible")
        return True
    except TimeoutError:
        return False
    except Exception as e:
        return False

async def wait_for_content_load(page, timeout=10000):
    """Wait for page content to stabilize"""
    try:
        # Wait for network to be idle
        await page.wait_for_load_state('networkidle', timeout=timeout)
        # Additional wait for dynamic content
        await asyncio.sleep(2)
        return True
    except Exception as e:
        return False

async def smart_scroll(page, max_scrolls=5):
    """Improved scrolling with better detection of new content"""
    previous_height = await page.evaluate("document.body.scrollHeight")
    
    for i in range(max_scrolls):
        # Scroll smoothly to avoid triggering anti-bot measures
        await page.evaluate("""
            window.scrollBy({
                top: window.innerHeight * 0.8,
                behavior: 'smooth'
            });
        """)
        
        # Wait for content to load
        await asyncio.sleep(SCROLL_PAUSE_TIME)
        
        # Check if new content loaded
        current_height = await page.evaluate("document.body.scrollHeight")
        if current_height > previous_height:
            previous_height = current_height
            return True  # New content found
        
        # If no new content, try a more aggressive scroll
        if i == max_scrolls - 1:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(SCROLL_PAUSE_TIME)
            
    return False  # No new content found

async def take_element_screenshot(element, filepath, retries=3):
    """Take screenshot with retry logic and proper error handling"""
    for attempt in range(retries):
        try:
            # Wait for element to be stable
            await element.wait_for(state="visible", timeout=5000)
            
            # Scroll element into view
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(1)  # Wait for scroll to complete
            
            # Take screenshot
            await element.screenshot(path=filepath, timeout=SCREENSHOT_TIMEOUT)
            return filepath
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                return ""
    return ""

async def wait_for_profile_load(page, username: str) -> bool:
    """Enhanced profile loading with better detection"""
    try:
        # Wait for either tweets, empty state, or protected account
        selectors_to_check = [
            'article[data-testid="tweet"]',
            'div[data-testid="emptyState"]',
            'div[data-testid="UserName"]',
            'div[data-testid="primaryColumn"]'
        ]
        
        # Try to find any of these elements
        for selector in selectors_to_check:
            try:
                await page.wait_for_selector(selector, timeout=10000)
                return True
            except TimeoutError:
                continue
        
        return False
        
    except Exception as e:
        return False

async def scrape_user_profile(page, username: str) -> dict:
    try:
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        
        if not await safe_wait_for_selector(page, 'div[data-testid="UserName"]', description="profile", timeout=10000):
            return {"username": username, "bio": ""}
        
        # Get display name
        display_name = ""
        try:
            name_element = page.locator('div[data-testid="UserName"] span').first
            if await name_element.count() > 0:
                display_name = await name_element.inner_text()
        except Exception as e:
            pass
        
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
                await asyncio.sleep(1)
            
        return {
            "username": display_name or username,
            "bio": bio
        }

    except Exception as e:
        return {"username": username, "bio": ""}

async def get_tweet_content(tweet_element) -> str:
    """Helper function to get tweet content from any tweet element"""
    try:
        content_element = tweet_element.locator('div[data-testid="tweetText"]').first
        if await content_element.count() > 0:
            return await content_element.inner_text()
    except Exception as e:
        pass
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
        pass
    return None

async def get_main_tweet_content(tweet_element) -> str:
    """Enhanced tweet content extraction with multiple fallback methods"""
    # Try multiple selectors in order of reliability
    content_selectors = [
        'div[data-testid="tweetText"]',
        'div[lang]:not([data-testid="UserDescription"])',
        'div[dir="auto"]:not([data-testid="UserDescription"])',
        'span[lang]'
    ]
    
    for selector in content_selectors:
        try:
            elements = tweet_element.locator(selector)
            count = await elements.count()
            
            if count > 0:
                # Get text from all matching elements and combine
                texts = []
                for i in range(count):
                    try:
                        text = await elements.nth(i).inner_text()
                        if text and text.strip():
                            texts.append(text.strip())
                    except Exception:
                        continue
                
                if texts:
                    combined_text = " ".join(texts)
                    # Filter out common non-content text
                    if (len(combined_text) > 3 and 
                        not combined_text.lower().startswith(('show this thread', 'see new tweets', 'following', 'follow'))):
                        return combined_text
                        
        except Exception:
            continue
    
    # Last resort: try to get any meaningful text
    try:
        all_text = await tweet_element.inner_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # Filter out UI elements and keep potential tweet content
        content_lines = []
        for line in lines:
            if (len(line) > 10 and 
                not line.lower().startswith(('retweet', 'reply', 'like', 'show this thread', 'follow'))):
                content_lines.append(line)
        
        if content_lines:
            return " ".join(content_lines[:3])  # Take first few lines only
            
    except Exception:
        pass
    
    return ""

async def get_tweet_id(tweet_element) -> str:
    """Enhanced tweet ID generation with multiple fallback methods"""
    # Method 1: Try to get tweet status ID from URL
    try:
        links = await tweet_element.locator('a[href*="/status/"]').all()
        for link in links:
            href = await link.get_attribute('href')
            if href and "/status/" in href:
                tweet_id = href.split('/status/')[-1].split('?')[0].split('/')[0]
                if tweet_id.isdigit() and len(tweet_id) > 10:
                    return f"status_{tweet_id}"
    except Exception:
        pass
    
    # Method 2: Try time element
    try:
        time_element = tweet_element.locator('time').first
        if await time_element.count() > 0:
            datetime_attr = await time_element.get_attribute('datetime')
            if datetime_attr:
                return f"time_{hashlib.md5(datetime_attr.encode()).hexdigest()[:12]}"
    except Exception:
        pass
    
    # Method 3: Create hash from text content and structure
    try:
        # Get text content
        text_content = await tweet_element.inner_text()
        
        # Get some structural identifiers
        structure_info = ""
        try:
            # Get user info
            user_elements = await tweet_element.locator('div[data-testid="User-Name"]').all()
            for user_el in user_elements:
                user_text = await user_el.inner_text()
                structure_info += user_text
        except:
            pass
        
        # Create a more robust hash
        combined_content = f"{text_content[:200]}_{structure_info}_{len(text_content)}"
        content_hash = hashlib.md5(combined_content.encode()).hexdigest()[:12]
        return f"hash_{content_hash}"
        
    except Exception:
        pass
    
    # Method 4: Last resort - timestamp based
    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(1000, 9999)
    return f"fallback_{timestamp}_{random_suffix}"

async def is_repost(tweet_element) -> bool:
    """Check if tweet is a repost (retweet without comment)"""
    try:
        # Method 1: Check for retweet indicator in the social context
        social_context = tweet_element.locator('div[data-testid="socialContext"]')
        if await social_context.count() > 0:
            social_text = await social_context.inner_text()
            if any(word.lower() in social_text.lower() for word in ["Reposted", "Retweeted"]):
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
                return True

        # Method 3: Check for retweet text in the article
        article_text = await tweet_element.inner_text()
        retweet_phrases = ["Retweeted", "Reposted", "Retweet", "reposted this", "retweeted this"]
        if any(phrase.lower() in article_text.lower() for phrase in retweet_phrases):
            return True

        # Method 4: Check for specific retweet structure
        try:
            nested_tweet = tweet_element.locator('div[data-testid="tweet"] div[data-testid="tweet"]')
            if await nested_tweet.count() > 0:
                return True
        except Exception:
            pass

        # Method 5: Check for retweet metadata
        try:
            time_element = tweet_element.locator('time')
            if await time_element.count() > 0:
                aria_label = await time_element.get_attribute('aria-label')
                if aria_label and any(word.lower() in aria_label.lower() for word in ["Retweeted", "Reposted"]):
                    return True
        except Exception:
            pass

    except Exception as e:
        pass
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
                content_elements = tweet_element.locator(selector)
                count = await content_elements.count()
                if count > 0:
                    # Join all text nodes if multiple elements are found
                    texts = []
                    for i in range(count):
                        try:
                            text = await content_elements.nth(i).inner_text()
                            if text:
                                texts.append(text)
                        except Exception:
                            continue
                    if texts:
                        main_content = "\n".join(texts)
                        break
            # Also try nested tweetText
            nested_tweet = tweet_element.locator('div[data-testid="tweet"] div[data-testid="tweetText"]')
            count_nested = await nested_tweet.count()
            if count_nested > 0:
                texts = []
                for i in range(count_nested):
                    try:
                        text = await nested_tweet.nth(i).inner_text()
                        if text:
                            texts.append(text)
                    except Exception:
                        continue
                if texts:
                    main_content = "\n".join(texts)
        except Exception as e:
            pass

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
            pass

        # Get bio
        bio = ""
        try:
            bio_element = tweet_element.locator('div[data-testid="UserDescription"]')
            if await bio_element.count() > 0:
                bio = await bio_element.inner_text()
        except Exception as e:
            pass

        return {
            "retweet_content": "",  # Pure retweets have no additional content
            "retweet_username": username,
            "retweet_profile_bio": bio,
            "retweet_main_content": main_content
        }

    except Exception as e:
        return None

async def scrape_tweets(page, username: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Enhanced tweet scraping with better performance and reliability"""
    tweets = []
    retweets = []
    processed_ids = set()
    
    try:
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=30000)
        
        if not await wait_for_profile_load(page, username):
            return tweets, retweets

        await wait_for_content_load(page)
        
        scroll_attempts = 0
        max_scroll_attempts = 20  # Limit scrolling attempts
        consecutive_no_new_content = 0
        max_consecutive_no_new = 3
        
        while (len(tweets) + len(retweets)) < MAX_TWEETS_PER_PROFILE and scroll_attempts < max_scroll_attempts:
            try:
                # Wait for tweets to load and stabilize
                await asyncio.sleep(2)
                
                # Get all visible tweet elements
                tweet_elements = await page.locator('article[data-testid="tweet"]').all()
                
                if not tweet_elements:
                    break

                initial_count = len(tweets) + len(retweets)
                processed_in_this_batch = 0

                # Process tweets in batches for better performance
                for idx, tweet_element in enumerate(tweet_elements):
                    try:
                        # Get unique tweet ID
                        tweet_id = await get_tweet_id(tweet_element)
                        
                        if tweet_id in processed_ids:
                            continue
                        
                        processed_ids.add(tweet_id)
                        processed_in_this_batch += 1
                        
                        # Check if it's a retweet first
                        if await is_repost(tweet_element):
                            
                            # Take screenshot with retry
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_retweet_{len(retweets)+1}_{tweet_id[:8]}.png")
                            screenshot_path = await take_element_screenshot(tweet_element, screenshot_path)
                            
                            # Get retweet info
                            retweet_info = await get_retweet_info(tweet_element)
                            if retweet_info:
                                retweet_info["retweet_screenshot"] = screenshot_path
                                retweets.append(retweet_info)
                            
                            continue

                        # Process as regular tweet
                        content = await get_main_tweet_content(tweet_element)
                        
                        if content and len(content.strip()) > 0:
                            # Take screenshot with retry
                            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{username}_tweet_{len(tweets)+1}_{tweet_id[:8]}.png")
                            screenshot_path = await take_element_screenshot(tweet_element, screenshot_path)
                            
                            tweet_data = {
                                "tweet_content": content,
                                "tweet_screenshot": screenshot_path,
                                "tweet_id": tweet_id
                            }

                            # Check for quoted tweet
                            quoted_info = await get_quoted_tweet_info(tweet_element)
                            if quoted_info:
                                tweet_data.update(quoted_info)

                            tweets.append(tweet_data)
                        else:
                            pass

                        # Check if we've reached the limit
                        if (len(tweets) + len(retweets)) >= MAX_TWEETS_PER_PROFILE:
                            break

                    except Exception as e:
                        continue

                current_count = len(tweets) + len(retweets)
                
                # Check if we found new content
                if current_count == initial_count or processed_in_this_batch == 0:
                    consecutive_no_new_content += 1
                else:
                    consecutive_no_new_content = 0

                # Stop if no new content for several attempts
                if consecutive_no_new_content >= max_consecutive_no_new:
                    break

                # Stop if we've reached the limit
                if current_count >= MAX_TWEETS_PER_PROFILE:
                    break

                # Smart scrolling
                scroll_success = await smart_scroll(page)
                scroll_attempts += 1
                
                if not scroll_success:
                    consecutive_no_new_content += 1

            except Exception as e:
                consecutive_no_new_content += 1

        
    except Exception as e:
        pass

    return tweets, retweets

async def scrape_likes(page, username: str) -> List[Dict]:
    """Likes scraping is currently disabled for performance"""
    return []

async def scrape_followers(page, username: str) -> List[Dict]:
    """Enhanced followers scraping with performance limits"""
    followers = []
    try:
        await page.goto(f"https://twitter.com/{username}/followers", wait_until="domcontentloaded")
        await wait_for_content_load(page)

        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 15  # Limit scroll attempts
        consecutive_no_new = 0
        max_consecutive_no_new = 3
        
        while len(followers) < MAX_FOLLOWERS and scroll_attempts < max_scroll_attempts:
            # Get all visible user cells
            cells = await page.locator('div[data-testid="cellInnerDiv"]').all()
            
            if not cells:
                consecutive_no_new += 1
                if consecutive_no_new >= max_consecutive_no_new:
                    break
                await asyncio.sleep(2)
                continue
            
            initial_count = len(followers)
            
            # Process visible cells
            for cell in cells:
                try:
                    if len(followers) >= MAX_FOLLOWERS:
                        break
                        
                    # Get username
                    username_found = ""
                    links = await cell.locator('a[role="link"]').all()
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and '/' in href and not href.startswith('http'):
                            potential_username = href.strip('/').split('/')[-1]
                            if potential_username and potential_username not in processed_usernames and not potential_username.startswith('i/'):
                                username_found = potential_username
                                break
                    
                    if not username_found or username_found in processed_usernames:
                        continue
                        
                    processed_usernames.add(username_found)
                    
                    # Get display name with enhanced selectors
                    name = ""
                    name_selectors = [
                        'div[data-testid="User-Name"] div:first-child span span',
                        'div[data-testid="User-Name"] div span',
                        'div[data-testid="User-Name"] span',
                        'a[role="link"] div span span'
                    ]
                    
                    for selector in name_selectors:
                        try:
                            name_element = cell.locator(selector).first
                            if await name_element.count() > 0:
                                name = await name_element.inner_text()
                                if name and not name.startswith('@'):
                                    break
                        except:
                            continue
                            
                    # Clean up name
                    if name:
                        name = name.strip().replace("·", "").strip()
                        
                    # Get bio with enhanced selectors
                    bio = ""
                    bio_selectors = [
                        'div[data-testid="UserDescription"]',
                        'div[data-testid="UserProfessionalCategory"]'
                    ]
                    
                    for selector in bio_selectors:
                        try:
                            bio_element = cell.locator(selector).first
                            if await bio_element.count() > 0:
                                bio = await bio_element.inner_text()
                                if bio:
                                    break
                        except:
                            continue
                            
                    # Clean up bio
                    if bio:
                        bio = bio.strip().replace("Follow", "").strip()
                        
                    # Add to followers list
                    followers.append({
                        "follower_name": name or username_found,
                        "follower_bio": bio or ""
                    })
                    
                except Exception as e:
                    continue
            
            # Check progress
            current_count = len(followers)
            if current_count == initial_count:
                consecutive_no_new += 1
            else:
                consecutive_no_new = 0
            
            # Stop if no new followers found
            if consecutive_no_new >= max_consecutive_no_new:
                break
            
            # Smart scroll for more content
            if len(followers) < MAX_FOLLOWERS:
                scroll_success = await smart_scroll(page, max_scrolls=2)
                scroll_attempts += 1
                
                if not scroll_success:
                    consecutive_no_new += 1

    except Exception as e:
        pass
        
    return followers

async def scrape_following(page, username: str) -> List[Dict]:
    """Enhanced following scraping with performance limits"""
    following = []
    try:
        await page.goto(f"https://twitter.com/{username}/following", wait_until="domcontentloaded")
        await wait_for_content_load(page)

        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 15  # Limit scroll attempts
        consecutive_no_new = 0
        max_consecutive_no_new = 3
        
        while len(following) < MAX_FOLLOWING and scroll_attempts < max_scroll_attempts:
            # Get all visible user cells
            cells = await page.locator('div[data-testid="cellInnerDiv"]').all()
            
            if not cells:
                consecutive_no_new += 1
                if consecutive_no_new >= max_consecutive_no_new:
                    break
                await asyncio.sleep(2)
                continue
            
            initial_count = len(following)
            
            # Process visible cells
            for cell in cells:
                try:
                    if len(following) >= MAX_FOLLOWING:
                        break
                        
                    # Get username
                    username_found = ""
                    links = await cell.locator('a[role="link"]').all()
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and '/' in href and not href.startswith('http'):
                            potential_username = href.strip('/').split('/')[-1]
                            if potential_username and potential_username not in processed_usernames and not potential_username.startswith('i/'):
                                username_found = potential_username
                                break
                    
                    if not username_found or username_found in processed_usernames:
                        continue
                        
                    processed_usernames.add(username_found)
                    
                    # Get display name with enhanced selectors
                    name = ""
                    name_selectors = [
                        'div[data-testid="User-Name"] div:first-child span span',
                        'div[data-testid="User-Name"] div span',
                        'div[data-testid="User-Name"] span',
                        'a[role="link"] div span span'
                    ]
                    
                    for selector in name_selectors:
                        try:
                            name_element = cell.locator(selector).first
                            if await name_element.count() > 0:
                                name = await name_element.inner_text()
                                if name and not name.startswith('@'):
                                    break
                        except:
                            continue
                            
                    # Clean up name
                    if name:
                        name = name.strip().replace("·", "").strip()
                        
                    # Get bio with enhanced selectors
                    bio = ""
                    bio_selectors = [
                        'div[data-testid="UserDescription"]',
                        'div[data-testid="UserProfessionalCategory"]'
                    ]
                    
                    for selector in bio_selectors:
                        try:
                            bio_element = cell.locator(selector).first
                            if await bio_element.count() > 0:
                                bio = await bio_element.inner_text()
                                if bio:
                                    break
                        except:
                            continue
                            
                    # Clean up bio
                    if bio:
                        bio = bio.strip().replace("Follow", "").strip()
                        
                    # Add to following list
                    following.append({
                        "following_name": name or username_found,
                        "following_bio": bio or ""
                    })
                    
                except Exception as e:
                    continue
            
            # Check progress
            current_count = len(following)
            if current_count == initial_count:
                consecutive_no_new += 1
            else:
                consecutive_no_new = 0
            
            # Stop if no new following found
            if consecutive_no_new >= max_consecutive_no_new:
                break
            
            # Smart scroll for more content
            if len(following) < MAX_FOLLOWING:
                scroll_success = await smart_scroll(page, max_scrolls=2)
                scroll_attempts += 1
                
                if not scroll_success:
                    consecutive_no_new += 1

    except Exception as e:
        pass
        
    return following

async def scrape_twitter(username: str) -> Dict:
    """Enhanced main scraping function with better performance and reliability"""
    result = {
        "user_profile": {"username": username, "bio": ""},
        "following": [],
        "followers": [],
        "tweets": [],
        "retweets": []
    }
    
    start_time = time.time()
    
    try:
        async with async_playwright() as p:
            # Launch browser with optimized settings
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-java',
                    '--disable-images',  # Disable image loading for faster performance
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )
            
            # Create context with optimized settings
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )
            
            # Load cookies
            if os.path.exists(COOKIES_FILE):
                try:
                    with open(COOKIES_FILE, "r") as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                except Exception as e:
                    await browser.close()
                    return result
            else:
                await browser.close()
                return result
            
            try:
                # Create main page
                page = await context.new_page()
                page.set_default_timeout(30000)
                
                # Verify login and access to Twitter
                try:
                    await page.goto("https://twitter.com", wait_until="domcontentloaded")
                    await wait_for_content_load(page, timeout=15000)
                    
                    # Quick login verification
                    login_indicators = [
                        'div[data-testid="AppTabBar_Home_Link"]',
                        'div[data-testid="SideNav_AccountSwitcher_Button"]',
                        'a[data-testid="AppTabBar_Profile_Link"]'
                    ]
                    
                    login_verified = False
                    for indicator in login_indicators:
                        if await page.locator(indicator).count() > 0:
                            login_verified = True
                            break
                    
                    if not login_verified:
                        pass  # Continue anyway
                        
                except Exception as e:
                    pass  # Continue with scraping attempt

                # Navigate to profile and verify accessibility
                try:
                    await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
                    await wait_for_content_load(page)
                    
                    # Check for profile accessibility
                    error_indicators = [
                        'div[data-testid="error-detail"]',
                        'div[data-testid="empty-state"]'
                    ]
                    
                    for indicator in error_indicators:
                        if await page.locator(indicator).count() > 0:
                            await browser.close()
                            return result
                    
                    # Verify profile loaded
                    if not await page.locator('div[data-testid="UserName"]').count() > 0:
                        await browser.close()
                        return result
                    
                except Exception as e:
                    await browser.close()
                    return result

                # Step 1: Get profile info
                result["user_profile"] = await scrape_user_profile(page, username)
                
                # Step 2: Get tweets and retweets
                tweets, retweets = await scrape_tweets(page, username)
                
                if tweets:
                    result["tweets"] = tweets
                    
                if retweets:
                    result["retweets"] = retweets
                
                # Step 3: Get followers (using a separate page for better performance)
                followers_page = await context.new_page()
                followers_page.set_default_timeout(30000)
                
                followers = await scrape_followers(followers_page, username)
                
                if followers:
                    result["followers"] = followers
                
                await followers_page.close()
                
                # Step 4: Get following (using a separate page for better performance)
                following_page = await context.new_page()
                following_page.set_default_timeout(30000)
                
                following = await scrape_following(following_page, username)
                
                if following:
                    result["following"] = following
                
                await following_page.close()
                
            except Exception as e:
                pass  # Silent error handling
            finally:
                await browser.close()
                    
    except Exception as e:
        pass  # Silent error handling
    
    # Save result as JSON file (optional, can be disabled)
    try:
        scraped_profiles_dir = os.path.join(os.path.dirname(__file__), '..', 'scraped_profiles')
        os.makedirs(scraped_profiles_dir, exist_ok=True)
        json_path = os.path.join(scraped_profiles_dir, f"{username}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass  # Silent error handling
    
    return result
