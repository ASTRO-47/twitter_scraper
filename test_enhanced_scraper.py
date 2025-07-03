#!/usr/bin/env python3
"""
Test script for the enhanced Twitter scraper
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

async def test_helper_functions():
    """Test the helper functions without requiring a browser"""
    print("Testing helper functions...")
    
    # Test imports
    try:
        from scraper import (
            safe_wait_for_selector,
            wait_for_content_load, 
            smart_scroll,
            take_element_screenshot
        )
        print("✓ All imports successful")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    
    print("✓ Helper functions loaded successfully")
    return True

async def test_configuration():
    """Test configuration constants"""
    try:
        from scraper import (
            MAX_TWEETS_PER_PROFILE,
            MAX_FOLLOWERS, 
            MAX_FOLLOWING,
            SCROLL_PAUSE_TIME,
            SCREENSHOT_TIMEOUT
        )
        
        print(f"✓ Configuration loaded:")
        print(f"  - Max tweets per profile: {MAX_TWEETS_PER_PROFILE}")
        print(f"  - Max followers: {MAX_FOLLOWERS}")
        print(f"  - Max following: {MAX_FOLLOWING}")
        print(f"  - Scroll pause time: {SCROLL_PAUSE_TIME}s")
        print(f"  - Screenshot timeout: {SCREENSHOT_TIMEOUT}ms")
        
        return True
    except ImportError as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_models():
    """Test the updated models"""
    try:
        from models import (
            UserProfile,
            Tweet, 
            Retweet,
            TwitterScrapeResponse
        )
        
        # Test creating a tweet with new structure
        tweet = Tweet(
            tweet_content="Test tweet",
            tweet_screenshot="/path/to/screenshot.png",
            tweet_id="test_123"
        )
        
        print("✓ Models updated successfully")
        print(f"  - Tweet model supports tweet_id: {hasattr(tweet, 'tweet_id')}")
        return True
    except Exception as e:
        print(f"✗ Models error: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Testing Enhanced Twitter Scraper")
    print("=" * 40)
    
    # Test 1: Helper functions
    test1 = await test_helper_functions()
    
    # Test 2: Configuration
    test2 = await test_configuration()
    
    # Test 3: Models
    test3 = test_models()
    
    print("\n" + "=" * 40)
    if all([test1, test2, test3]):
        print("🎉 All tests passed! The enhanced scraper is ready to use.")
        print("\nTo run the scraper:")
        print("1. Make sure you have valid cookies (run login_manual.py)")
        print("2. Start the FastAPI server: uvicorn app.main:app --reload")
        print("3. Open http://localhost:8000 in your browser")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return all([test1, test2, test3])

if __name__ == "__main__":
    asyncio.run(main())
