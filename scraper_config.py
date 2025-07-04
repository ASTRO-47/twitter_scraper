# Twitter Scraper Configuration
# Adjust these values to control scraping speed and limits

# Performance Settings
MAX_TWEETS_PER_PROFILE = 30  # Reduce for faster scraping
MAX_FOLLOWERS = 50           # Reduce for faster scraping
MAX_FOLLOWING = 50           # Reduce for faster scraping
SCROLL_PAUSE_TIME = 1.0      # Reduce for faster scraping (minimum 0.5)
SCREENSHOT_TIMEOUT = 3000    # Reduce for faster screenshots

# Feature Settings
ENABLE_SCREENSHOTS = True    # Set to False for much faster scraping
ENABLE_FOLLOWERS = True      # Set to False to skip followers scraping
ENABLE_FOLLOWING = True      # Set to False to skip following scraping

# Advanced Settings
MAX_SCROLL_ATTEMPTS = 5      # Reduce for faster scraping
MAX_CONSECUTIVE_NO_NEW = 2   # Reduce for faster scraping

# Speed Presets:
# ULTRA_FAST: MAX_TWEETS=10, MAX_FOLLOWERS=20, MAX_FOLLOWING=20, ENABLE_SCREENSHOTS=False
# FAST: MAX_TWEETS=30, MAX_FOLLOWERS=50, MAX_FOLLOWING=50, ENABLE_SCREENSHOTS=True
# BALANCED: MAX_TWEETS=50, MAX_FOLLOWERS=100, MAX_FOLLOWING=100, ENABLE_SCREENSHOTS=True
# THOROUGH: MAX_TWEETS=100, MAX_FOLLOWERS=200, MAX_FOLLOWING=200, ENABLE_SCREENSHOTS=True
