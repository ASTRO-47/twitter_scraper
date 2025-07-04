import os
import json
import asyncio
import random
import hashlib
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, TimeoutError

# Try to import custom config, fall back to defaults
try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from scraper_config import *
except ImportError:
    # Default configuration
    MAX_TWEETS_PER_PROFILE = 30
    MAX_FOLLOWERS = 50
    MAX_FOLLOWING = 50
    SCROLL_PAUSE_TIME = 1.0
    SCREENSHOT_TIMEOUT = 3000
    ENABLE_SCREENSHOTS = True
    ENABLE_FOLLOWERS = True
    ENABLE_FOLLOWING = True
    MAX_SCROLL_ATTEMPTS = 5
    MAX_CONSECUTIVE_NO_NEW = 2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "twitter_cookies.json")

async def safe_wait_for_selector(page, selector, timeout=15000, description="element"):
    """Enhanced wait function with better error handling"""
    try:
        logger.info(f"Waiting for {description} with selector: {selector}")
        await page.wait_for_selector(selector, timeout=timeout, state="visible")
        logger.info(f"✅ Found {description}")
        return True
    except TimeoutError:
        logger.warning(f"❌ Timeout waiting for {description} with selector: {selector}")
        return False
    except Exception as e:
        logger.error(f"❌ Error waiting for {description}: {str(e)}")
        return False

async def wait_for_content_load(page, timeout=5000):
    """Wait for page content to stabilize - reduced timeout"""
    try:
        logger.info("Waiting for page content to load...")
        # Wait for network to be idle with reduced timeout
        await page.wait_for_load_state('networkidle', timeout=timeout)
        # Reduced wait for dynamic content
        await asyncio.sleep(1)
        logger.info("✅ Page content loaded")
        return True
    except Exception as e:
        logger.warning(f"❌ Error waiting for content load: {str(e)}")
        return False

async def smart_scroll(page, max_scrolls=3):
    """Improved scrolling with better detection of new content - reduced scrolls"""
    previous_height = await page.evaluate("document.body.scrollHeight")
    
    for i in range(max_scrolls):
        # Scroll smoothly to avoid triggering anti-bot measures
        await page.evaluate("""
            window.scrollBy({
                top: window.innerHeight * 0.8,
                behavior: 'smooth'
            });
        """)
        
        # Reduced wait for content to load
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

async def take_element_screenshot(element, filepath, retries=2):
    """Take screenshot with retry logic and proper error handling - reduced retries"""
    # Skip screenshots if disabled for faster scraping
    if not ENABLE_SCREENSHOTS:
        logger.info("📸 Screenshots disabled - skipping")
        return ""
    
    # Check if screenshot already exists to prevent duplicates
    if os.path.exists(filepath):
        logger.info(f"🔄 Screenshot already exists: {filepath}")
        return filepath
    
    logger.info(f"📸 Taking screenshot: {filepath}")
    
    for attempt in range(retries):
        try:
            # Wait for element to be stable with reduced timeout
            await element.wait_for(state="visible", timeout=3000)
            
            # Scroll element into view
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)  # Reduced wait for scroll to complete
            
            # Take screenshot
            await element.screenshot(path=filepath, timeout=SCREENSHOT_TIMEOUT)
            logger.info(f"✅ Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.warning(f"❌ Screenshot attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:
                await asyncio.sleep(1)  # Reduced retry wait
            else:
                logger.error(f"❌ Failed to take screenshot after {retries} attempts")
                return ""
    return ""

def generate_unique_screenshot_filename(username: str, tweet_type: str, content: str) -> str:
    """Generate unique screenshot filename to prevent duplicates"""
    # Create hash from content to ensure uniqueness
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    timestamp = int(time.time())
    filename = f"{username}_{tweet_type}_{content_hash}_{timestamp}.png"
    return os.path.join(SCREENSHOTS_DIR, filename)

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
    logger.info(f"📋 Scraping profile for: {username}")
    try:
        logger.info(f"🔄 Navigating to profile: https://twitter.com/{username}")
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        
        if not await safe_wait_for_selector(page, 'div[data-testid="UserName"]', description="profile", timeout=10000):
            logger.error(f"❌ Could not find profile for {username}")
            return {"username": username, "bio": ""}
        
        # Get display name
        display_name = ""
        try:
            name_element = page.locator('div[data-testid="UserName"] span').first
            if await name_element.count() > 0:
                display_name = await name_element.inner_text()
                logger.info(f"✅ Display name found: {display_name}")
        except Exception as e:
            logger.warning(f"❌ Error getting display name: {str(e)}")
        
        # Get bio with retry
        bio = ""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                bio_element = page.locator('div[data-testid="UserDescription"]')
                if await bio_element.count() > 0:
                    bio = await bio_element.inner_text()
                    if bio:
                        logger.info(f"✅ Bio found: {bio[:100]}...")
                        break
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"❌ Bio attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(1)
            
        return {
            "username": display_name or username,
            "bio": bio
        }

    except Exception as e:
        logger.error(f"❌ Error scraping profile for {username}: {str(e)}")
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
            "content": main_content,  # For unique filename generation
            "retweet_content": "",  # Pure retweets have no additional content
            "retweet_username": username,
            "retweet_profile_bio": bio,
            "retweet_main_content": main_content
        }

    except Exception as e:
        return None

async def scrape_tweets(page, username: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Enhanced tweet scraping with better performance and reliability"""
    logger.info(f"🐦 Starting tweet scraping for: {username}")
    tweets = []
    retweets = []
    processed_ids = set()
    
    try:
        logger.info(f"🔄 Navigating to profile: https://twitter.com/{username}")
        await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=30000)
        
        if not await wait_for_profile_load(page, username):
            logger.error(f"❌ Profile failed to load for {username}")
            return tweets, retweets

        await wait_for_content_load(page)
        
        scroll_attempts = 0
        max_scroll_attempts = MAX_SCROLL_ATTEMPTS  # Use config value
        consecutive_no_new_content = 0
        max_consecutive_no_new = MAX_CONSECUTIVE_NO_NEW  # Use config value
        
        logger.info(f"🔄 Starting tweet collection (max {MAX_TWEETS_PER_PROFILE} tweets)")
        
        while (len(tweets) + len(retweets)) < MAX_TWEETS_PER_PROFILE and scroll_attempts < max_scroll_attempts:
            try:
                # Reduced wait for tweets to load and stabilize
                await asyncio.sleep(1)
                
                # Get all visible tweet elements
                tweet_elements = await page.locator('article[data-testid="tweet"]').all()
                
                if not tweet_elements:
                    logger.warning("❌ No tweet elements found")
                    break

                logger.info(f"🔍 Found {len(tweet_elements)} tweet elements on page")
                
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
                            logger.info(f"🔄 Processing retweet {len(retweets)+1}")
                            
                            # Get retweet content for unique filename
                            retweet_info = await get_retweet_info(tweet_element)
                            if retweet_info and retweet_info.get("content"):
                                # Generate unique screenshot filename
                                screenshot_path = generate_unique_screenshot_filename(
                                    username, "retweet", retweet_info["content"]
                                )
                                screenshot_path = await take_element_screenshot(tweet_element, screenshot_path)
                                
                                retweet_info["retweet_screenshot"] = screenshot_path
                                retweets.append(retweet_info)
                                logger.info(f"✅ Retweet {len(retweets)} saved")
                            else:
                                logger.warning(f"❌ Could not get retweet info")
                            
                            continue

                        # Process as regular tweet
                        content = await get_main_tweet_content(tweet_element)
                        
                        if content and len(content.strip()) > 0:
                            logger.info(f"🐦 Processing tweet {len(tweets)+1}: {content[:50]}...")
                            
                            # Generate unique screenshot filename
                            screenshot_path = generate_unique_screenshot_filename(
                                username, "tweet", content
                            )
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
                                logger.info(f"📝 Found quoted tweet in tweet {len(tweets)+1}")

                            tweets.append(tweet_data)
                            logger.info(f"✅ Tweet {len(tweets)} saved")
                        else:
                            logger.warning(f"❌ Empty content for tweet {idx+1}")

                        # Check if we've reached the limit
                        if (len(tweets) + len(retweets)) >= MAX_TWEETS_PER_PROFILE:
                            logger.info(f"🏁 Reached maximum tweets limit ({MAX_TWEETS_PER_PROFILE})")
                            break

                    except Exception as e:
                        logger.error(f"❌ Error processing tweet {idx+1}: {str(e)}")
                        continue

                current_count = len(tweets) + len(retweets)
                logger.info(f"📊 Batch complete: {current_count} total items ({len(tweets)} tweets, {len(retweets)} retweets)")
                
                # Check if we found new content
                if current_count == initial_count or processed_in_this_batch == 0:
                    consecutive_no_new_content += 1
                    logger.warning(f"❌ No new content found (attempt {consecutive_no_new_content}/{max_consecutive_no_new})")
                else:
                    consecutive_no_new_content = 0

                # Stop if no new content for several attempts
                if consecutive_no_new_content >= max_consecutive_no_new:
                    logger.info(f"🔚 Stopping due to no new content for {max_consecutive_no_new} consecutive attempts")
                    break

                # Stop if we've reached the limit
                if current_count >= MAX_TWEETS_PER_PROFILE:
                    break

                # Smart scrolling with reduced attempts
                logger.info(f"📜 Scrolling for more content (attempt {scroll_attempts + 1}/{max_scroll_attempts})")
                scroll_success = await smart_scroll(page, max_scrolls=2)  # Reduced max scrolls
                scroll_attempts += 1
                
                if not scroll_success:
                    consecutive_no_new_content += 1
                    logger.warning(f"❌ Scroll did not load new content")

            except Exception as e:
                logger.error(f"❌ Error in tweet scraping loop: {str(e)}")
                consecutive_no_new_content += 1

        logger.info(f"🏁 Tweet scraping complete: {len(tweets)} tweets, {len(retweets)} retweets")
        
    except Exception as e:
        logger.error(f"❌ Critical error in tweet scraping: {str(e)}")

    return tweets, retweets

async def scrape_likes(page, username: str) -> List[Dict]:
    """Likes scraping is currently disabled for performance"""
    return []

async def scrape_followers(page, username: str) -> List[Dict]:
    """Enhanced followers scraping with performance limits"""
    logger.info(f"👥 Starting followers scraping for: {username}")
    followers = []
    try:
        await page.goto(f"https://twitter.com/{username}/followers", wait_until="domcontentloaded")
        await wait_for_content_load(page)

        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 8  # Reduced scroll attempts
        consecutive_no_new = 0
        max_consecutive_no_new = 2  # Reduced threshold
        
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
                scroll_success = await smart_scroll(page, max_scrolls=1)  # Reduced max scrolls
                scroll_attempts += 1
                
                if not scroll_success:
                    consecutive_no_new += 1

    except Exception as e:
        logger.error(f"❌ Error scraping followers: {str(e)}")
        
    logger.info(f"✅ Followers scraping complete: {len(followers)} followers")
    return followers

async def scrape_following(page, username: str) -> List[Dict]:
    """Enhanced following scraping with performance limits"""
    logger.info(f"👤 Starting following scraping for: {username}")
    following = []
    try:
        await page.goto(f"https://twitter.com/{username}/following", wait_until="domcontentloaded")
        await wait_for_content_load(page)

        processed_usernames = set()
        scroll_attempts = 0
        max_scroll_attempts = 8  # Reduced scroll attempts
        consecutive_no_new = 0
        max_consecutive_no_new = 2  # Reduced threshold
        
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
                scroll_success = await smart_scroll(page, max_scrolls=1)  # Reduced max scrolls
                scroll_attempts += 1
                
                if not scroll_success:
                    consecutive_no_new += 1

    except Exception as e:
        logger.error(f"❌ Error scraping following: {str(e)}")
        
    logger.info(f"✅ Following scraping complete: {len(following)} following")
    return following

async def scrape_twitter(username: str) -> Dict:
    """Enhanced main scraping function with better performance and reliability"""
    logger.info(f"🚀 Starting Twitter scraping for user: {username}")
    
    # Log current configuration
    logger.info("⚙️ Current Configuration:")
    logger.info(f"  📊 Max tweets: {MAX_TWEETS_PER_PROFILE}")
    logger.info(f"  👥 Max followers: {MAX_FOLLOWERS}")
    logger.info(f"  👤 Max following: {MAX_FOLLOWING}")
    logger.info(f"  📸 Screenshots: {'Enabled' if ENABLE_SCREENSHOTS else 'Disabled'}")
    logger.info(f"  👥 Followers scraping: {'Enabled' if ENABLE_FOLLOWERS else 'Disabled'}")
    logger.info(f"  👤 Following scraping: {'Enabled' if ENABLE_FOLLOWING else 'Disabled'}")
    
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
            logger.info("🔄 Launching browser...")
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
            
            logger.info("🔄 Creating browser context...")
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
                    logger.info("🔄 Loading Twitter cookies...")
                    with open(COOKIES_FILE, "r") as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    logger.info("✅ Cookies loaded successfully")
                except Exception as e:
                    logger.error(f"❌ Error loading cookies: {str(e)}")
                    await browser.close()
                    return result
            else:
                logger.error("❌ No cookies file found - login required")
                await browser.close()
                return result
            
            try:
                # Create main page
                page = await context.new_page()
                page.set_default_timeout(15000)  # Reduced timeout
                
                # Verify login and access to Twitter
                try:
                    logger.info("🔄 Verifying login status...")
                    await page.goto("https://twitter.com", wait_until="domcontentloaded")
                    await wait_for_content_load(page, timeout=8000)  # Reduced timeout
                    
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
                            logger.info("✅ Login verified successfully")
                            break
                    
                    if not login_verified:
                        logger.warning("❌ Login verification failed - continuing anyway")
                        
                except Exception as e:
                    logger.error(f"❌ Error during login verification: {str(e)}")

                # Navigate to profile and verify accessibility
                try:
                    logger.info(f"🔄 Navigating to profile: {username}")
                    await page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded")
                    await wait_for_content_load(page)
                    
                    # Check for profile accessibility
                    error_indicators = [
                        'div[data-testid="error-detail"]',
                        'div[data-testid="empty-state"]'
                    ]
                    
                    for indicator in error_indicators:
                        if await page.locator(indicator).count() > 0:
                            logger.error(f"❌ Profile not accessible: {username}")
                            await browser.close()
                            return result
                    
                    # Verify profile loaded
                    if not await page.locator('div[data-testid="UserName"]').count() > 0:
                        logger.error(f"❌ Profile did not load properly: {username}")
                        await browser.close()
                        return result
                    
                    logger.info("✅ Profile loaded successfully")
                    
                except Exception as e:
                    logger.error(f"❌ Error accessing profile: {str(e)}")
                    await browser.close()
                    return result

                # Step 1: Get profile info
                logger.info("📋 Step 1: Getting profile information...")
                result["user_profile"] = await scrape_user_profile(page, username)
                
                # Step 2: Get tweets and retweets
                logger.info("🐦 Step 2: Getting tweets and retweets...")
                tweets, retweets = await scrape_tweets(page, username)
                
                if tweets:
                    result["tweets"] = tweets
                    logger.info(f"✅ Found {len(tweets)} tweets")
                    
                if retweets:
                    result["retweets"] = retweets
                    logger.info(f"✅ Found {len(retweets)} retweets")
                
                # Skip followers/following if disabled in config
                if not ENABLE_FOLLOWERS and not ENABLE_FOLLOWING:
                    logger.info("👥👤 Followers and Following scraping disabled in config")
                elif not ENABLE_FOLLOWERS:
                    logger.info("👤 Step 4: Getting following only...")
                    following_page = await context.new_page()
                    following_page.set_default_timeout(15000)
                    
                    following = await scrape_following(following_page, username)
                    if following:
                        result["following"] = following
                        logger.info(f"✅ Found {len(following)} following")
                    
                    await following_page.close()
                elif not ENABLE_FOLLOWING:
                    logger.info("👥 Step 3: Getting followers only...")
                    followers_page = await context.new_page()
                    followers_page.set_default_timeout(15000)
                    
                    followers = await scrape_followers(followers_page, username)
                    if followers:
                        result["followers"] = followers
                        logger.info(f"✅ Found {len(followers)} followers")
                    
                    await followers_page.close()
                else:
                    # Steps 3 & 4: Get followers and following in parallel for better performance
                    logger.info("👥👤 Steps 3 & 4: Getting followers and following in parallel...")
                    
                    # Create separate pages for parallel execution
                    followers_page = await context.new_page()
                    followers_page.set_default_timeout(15000)  # Reduced timeout
                    
                    following_page = await context.new_page()
                    following_page.set_default_timeout(15000)  # Reduced timeout
                    
                    # Run followers and following scraping in parallel
                    try:
                        followers_task = asyncio.create_task(scrape_followers(followers_page, username))
                        following_task = asyncio.create_task(scrape_following(following_page, username))
                        
                        # Wait for both tasks to complete with a timeout
                        followers, following = await asyncio.wait_for(
                            asyncio.gather(followers_task, following_task), 
                            timeout=60  # 1 minute timeout for both operations
                        )
                        
                        if followers:
                            result["followers"] = followers
                            logger.info(f"✅ Found {len(followers)} followers")
                        
                        if following:
                            result["following"] = following
                            logger.info(f"✅ Found {len(following)} following")
                            
                    except asyncio.TimeoutError:
                        logger.warning("❌ Followers/Following scraping timed out")
                    except Exception as e:
                        logger.error(f"❌ Error in parallel scraping: {str(e)}")
                    finally:
                        await followers_page.close()
                        await following_page.close()
                
            except Exception as e:
                logger.error(f"❌ Error during scraping: {str(e)}")
            finally:
                await browser.close()
                logger.info("🔄 Browser closed")
                    
    except Exception as e:
        logger.error(f"❌ Critical error in scraping: {str(e)}")
    
    # Calculate total time
    total_time = time.time() - start_time
    logger.info(f"🏁 Scraping complete in {total_time:.2f} seconds")
    
    # Save result as JSON file (optional, can be disabled)
    try:
        scraped_profiles_dir = os.path.join(os.path.dirname(__file__), '..', 'scraped_profiles')
        os.makedirs(scraped_profiles_dir, exist_ok=True)
        json_path = os.path.join(scraped_profiles_dir, f"{username}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Results saved to: {json_path}")
    except Exception as e:
        logger.error(f"❌ Error saving results: {str(e)}")
    
    return result
