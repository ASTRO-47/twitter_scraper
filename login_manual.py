import os
import json
import time


from playwright.sync_api import sync_playwright

# Define the paths
PROFILE_DIR = "/home/astro/Desktop/twitter_scraper/playwright_profile"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "app", "twitter_cookies.json")

def save_cookies(context):
    cookies = context.cookies()
    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)
    print(f"Cookies saved to {COOKIES_FILE}")

with sync_playwright() as p:
    # Launch the browser with a new context
    browser = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,  # Must be False to allow manual login
        viewport={'width': 1280, 'height': 720},
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-extensions']
    )
    
    page = browser.new_page()
    
    # Set longer timeouts for slow machines
    page.set_default_timeout(60000)  # 60 seconds timeout
    
    # Go to Twitter login page
    print("Navigating to Twitter login page...")
    page.goto("https://twitter.com/i/flow/login", timeout=60000, wait_until="domcontentloaded")
    
    print("\nPlease follow these steps:")
    print("1. Log in to Twitter in the opened browser")
    print("2. Wait until you see your Twitter home feed")
    print("3. Press Enter in this terminal to save the session")
    
    input("\nPress Enter after you have successfully logged in and can see your Twitter feed...")
    
    # Verify login status with better error handling for slow machines
    print("Verifying login status (this may take a while on slow machines)...")
    try:
        # Try to navigate to home page with longer timeout for slow machines
        print("Navigating to home page...")
        page.goto("https://twitter.com/home", timeout=60000, wait_until="domcontentloaded")
        print("Page loaded, waiting for content...")
        time.sleep(5)  # Give slow machine more time to load
        
        # Check for login indicators
        login_successful = False
        
        # Method 1: Check for primary column (timeline)
        print("Checking for timeline...")
        try:
            page.wait_for_selector('div[data-testid="primaryColumn"]', timeout=15000)
            print("✅ Login verified - timeline found")
            login_successful = True
        except:
            print("Timeline not found, trying other methods...")
        
        # Method 2: Check for profile link
        if not login_successful:
            print("Checking for profile link...")
            try:
                page.wait_for_selector('a[data-testid="AppTabBar_Profile_Link"]', timeout=15000)
                print("✅ Login verified - profile link found")
                login_successful = True
            except:
                print("Profile link not found, trying other methods...")
        
        # Method 3: Check for absence of login button
        if not login_successful:
            print("Checking for login button...")
            try:
                login_button = page.locator('a[href="/login"]')
                if login_button.count() == 0:
                    print("✅ Login verified - no login button found")
                    login_successful = True
                else:
                    print("❌ Login button still present")
            except:
                print("Could not check for login button...")
        
        if login_successful:
            print("Login successful! Saving cookies...")
            save_cookies(browser)
        else:
            print("❌ Could not verify login status. This is common on slow machines.")
            print("You can still try to save cookies manually.")
            
            # Ask user if they want to save cookies anyway
            save_anyway = input("Do you want to save cookies anyway? (y/n): ").lower().strip()
            if save_anyway == 'y':
                save_cookies(browser)
                print("Cookies saved (unverified login status)")
            else:
                print("Cookies not saved")
                
    except Exception as e:
        print(f"❌ Error during login verification: {str(e)}")
        print("This is likely due to the slow machine. You can still save cookies.")
        
        # Ask user if they want to save cookies anyway
        save_anyway = input("Do you want to save cookies anyway? (y/n): ").lower().strip()
        if save_anyway == 'y':
            save_cookies(browser)
            print("Cookies saved (verification failed due to slow machine)")
        else:
            print("Cookies not saved")
    
    browser.close()