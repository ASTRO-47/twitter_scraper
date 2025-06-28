import os
import json
from playwright.sync_api import sync_playwright

# Define the paths
PROFILE_DIR = "/home/iez-zagh/Desktop/twitter_scraper/playwright_profile"
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
        headless=False,
        viewport={'width': 1280, 'height': 720}
    )
    
    page = browser.new_page()
    
    # Go to Twitter login page
    page.goto("https://twitter.com/i/flow/login")
    
    print("\nPlease follow these steps:")
    print("1. Log in to Twitter in the opened browser")
    print("2. Wait until you see your Twitter home feed")
    print("3. Press Enter in this terminal to save the session")
    
    input("\nPress Enter after you have successfully logged in and can see your Twitter feed...")
    
    # Verify login status
    page.goto("https://twitter.com/home")
    try:
        # Wait for a element that's only visible when logged in
        page.wait_for_selector('div[data-testid="primaryColumn"]', timeout=5000)
        print("Login successful!")
        # Save the cookies
        save_cookies(browser)
    except Exception as e:
        print("Error: Login verification failed. Please make sure you're properly logged in before pressing Enter.")
        print(f"Error details: {str(e)}")
    
    browser.close()