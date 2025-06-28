import asyncio
import json
from app.scraper import scrape_twitter
import webbrowser
from urllib.parse import quote

async def test_scraper(username: str):
    print(f"\n=== Testing Twitter Scraper for @{username} ===\n")
    
    # First open the profile in a browser for manual comparison
    profile_url = f"https://twitter.com/{username}"
    print(f"Opening profile in browser for reference: {profile_url}")
    webbrowser.open(profile_url)
    
    # Run the scraper
    print("\nRunning scraper...")
    result = await scrape_twitter(username)
    
    # Save results to a file for analysis
    output_file = f"scrape_results_{username}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # Print analysis
    print("\n=== Scraping Results Analysis ===")
    print(f"Results saved to: {output_file}")
    print("\nProfile Info:")
    print(f"Username: {result['user_profile']['username']}")
    print(f"Bio: {result['user_profile']['bio']}")
    
    print("\nContent Counts:")
    print(f"Regular Tweets: {len(result['tweets'])}")
    print(f"Retweets: {len(result['retweets'])}")
    
    # Analyze tweets
    print("\nTweet Analysis:")
    empty_tweets = sum(1 for t in result['tweets'] if not t['tweet_content'])
    print(f"Empty tweets: {empty_tweets}")
    
    # Analyze retweets
    print("\nRetweet Analysis:")
    empty_retweets = sum(1 for rt in result['retweets'] if not rt['retweet_main_content'])
    print(f"Empty retweets: {empty_retweets}")
    
    print("\nFirst few tweets:")
    for i, tweet in enumerate(result['tweets'][:3], 1):
        print(f"\nTweet {i}:")
        print(f"Content: {tweet['tweet_content'][:100]}...")
        print(f"Screenshot: {tweet['tweet_screenshot']}")
    
    print("\nFirst few retweets:")
    for i, retweet in enumerate(result['retweets'][:3], 1):
        print(f"\nRetweet {i}:")
        print(f"Username: {retweet['retweet_username']}")
        print(f"Content: {retweet['retweet_main_content'][:100]}...")
        print(f"Screenshot: {retweet['retweet_screenshot']}")
    
    print("\n=== Verification Steps ===")
    print("1. Check the browser to verify the profile's actual content")
    print("2. Compare the counts with what you see on Twitter")
    print("3. Verify that retweets are properly identified")
    print("4. Check if any tweets are misclassified")
    print("5. Look for any missing content")
    
    return result

if __name__ == "__main__":
    # Test with a specific username
    username = input("Enter Twitter username to test (without @): ").strip()
    asyncio.run(test_scraper(username)) 