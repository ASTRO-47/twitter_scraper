#!/usr/bin/env python3
import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIES_FILE = "/root/twitter_scraper/app/twitter_cookies.json"

async def test_cookies_loading():
    """Test if cookies are loaded correctly and authentication works"""
    print("Testing cookies loading and authentication...")
    
    try:
        async with async_playwright() as p:
            # Launch browser in headed mode so UI is visible
            browser = await p.chromium.launch(
                headless=False,  # Show browser window
                args=['--disable-extensions', '--no-sandbox', '--disable-dev-shm-usage']
            )
            
            # Create context
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            )
            
            # Check if cookies file exists
            if not os.path.exists(COOKIES_FILE):
                print(f"❌ Cookies file not found at: {COOKIES_FILE}")
                return False
            
            print(f"✅ Cookies file found at: {COOKIES_FILE}")
            
            # Load cookies
            try:
                with open(COOKIES_FILE, "r") as f:
                    cookies = json.load(f)
                
                print(f"✅ Successfully loaded {len(cookies)} cookies from file")
                
                # Check for essential cookies
                essential_cookies = ['auth_token', 'ct0', 'twid']
                found_cookies = [cookie['name'] for cookie in cookies]
                
                for essential in essential_cookies:
                    if essential in found_cookies:
                        print(f"✅ Found essential cookie: {essential}")
                    else:
                        print(f"❌ Missing essential cookie: {essential}")
                
                # Add cookies to context
                await context.add_cookies(cookies)
                print("✅ Cookies added to browser context")
                
            except Exception as e:
                print(f"❌ Error loading cookies: {str(e)}")
                await browser.close()
                return False
            
            # Create page and test authentication
            page = await context.new_page()
            page.set_default_timeout(30000)
            
            try:
                print("\n🌐 Navigating to Twitter...")
                await page.goto("https://twitter.com", wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                # Check for login state
                print("🔍 Checking authentication status...")
                
                # Check for login button (should not be present if logged in)
                login_button = page.locator('a[href="/login"]')
                if await login_button.count() > 0:
                    print("❌ Not logged in - login button found")
                    await browser.close()
                    return False
                
                # Check for sign up button (should not be present if logged in)
                signup_button = page.locator('a[href="/i/flow/signup"]')
                if await signup_button.count() > 0:
                    print("❌ Not logged in - signup button found")
                    await browser.close()
                    return False
                
                # Check for home timeline (should be present if logged in)
                timeline = page.locator('div[data-testid="primaryColumn"]')
                if await timeline.count() > 0:
                    print("✅ Successfully authenticated - home timeline found")
                else:
                    print("❌ Could not verify authentication - no timeline found")
                    await browser.close()
                    return False
                
                # Try to get user info
                try:
                    # Look for user menu or profile link
                    profile_link = page.locator('a[data-testid="AppTabBar_Profile_Link"]')
                    if await profile_link.count() > 0:
                        print("✅ Profile link found - authentication confirmed")
                        
                        # Get the href to see the username
                        href = await profile_link.get_attribute('href')
                        if href:
                            username = href.split('/')[-1]
                            print(f"✅ Logged in as: @{username}")
                    else:
                        print("⚠️  Profile link not found, but timeline is present")
                        
                except Exception as e:
                    print(f"⚠️  Could not get user info: {str(e)}")
                
                print("\n✅ Cookie loading and authentication test PASSED!")
                
            except Exception as e:
                print(f"❌ Error during authentication test: {str(e)}")
                await browser.close()
                return False
            finally:
                await browser.close()
                
    except Exception as e:
        print(f"❌ Critical error: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_cookies_loading()) 