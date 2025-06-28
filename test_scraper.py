import asyncio
import json
import os
from datetime import datetime
from app.scraper import scrape_twitter

# Create results directory
RESULTS_DIR = "test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def save_json(data, filename):
    """Save data as formatted JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def print_header(text):
    """Print a section header"""
    print(f"\n{'='*10} {text} {'='*10}")

def analyze_content(items: list, item_type: str) -> dict:
    """Analyze a list of items for common issues"""
    return {
        "total": len(items),
        "empty_content": sum(1 for i in items if not i.get(f"{item_type}_content", "")),
        "missing_username": sum(1 for i in items if not i.get(f"{item_type}_username", "")),
        "missing_bio": sum(1 for i in items if not i.get(f"{item_type}_profile_bio", "")),
        "missing_screenshots": sum(1 for i in items if not i.get(f"{item_type}_screenshot", ""))
    }

async def test_profile(username: str):
    """Test scraper on a single profile"""
    try:
        # Setup test directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_dir = os.path.join(RESULTS_DIR, f"{username}_{timestamp}")
        os.makedirs(test_dir, exist_ok=True)

        print_header(f"Testing @{username}")
        print(f"Results will be saved in: {test_dir}")

        # Run scraper
        print("\nScraping profile...")
        result = await scrape_twitter(username)

        # Save raw results
        results_file = os.path.join(test_dir, "results.json")
        save_json(result, results_file)

        # Analyze results
        print_header("Results Summary")
        
        # Profile info
        print("\nProfile:")
        print(f"Username: {result['user_profile']['username']}")
        print(f"Bio: {result['user_profile']['bio']}")

        # Tweet stats
        tweets = result['tweets']
        print("\nTweets:")
        print(f"Total tweets: {len(tweets)}")
        print(f"Empty tweets: {sum(1 for t in tweets if not t['tweet_content'])}")
        print(f"Tweets with quotes: {sum(1 for t in tweets if 'quoted_content' in t)}")

        # Retweet analysis
        retweets = result['retweets']
        retweet_stats = analyze_content(retweets, "retweet")
        print("\nRetweets:")
        print(f"Total retweets: {retweet_stats['total']}")
        print(f"Empty retweets: {retweet_stats['empty_content']}")
        print(f"Missing usernames: {retweet_stats['missing_username']}")
        print(f"Missing bios: {retweet_stats['missing_bio']}")
        print(f"Missing screenshots: {retweet_stats['missing_screenshots']}")

        # Likes analysis
        likes = result['likes']
        likes_stats = analyze_content(likes, "liked_tweet")
        print("\nLikes:")
        print(f"Total likes: {likes_stats['total']}")
        print(f"Empty likes: {likes_stats['empty_content']}")
        print(f"Missing usernames: {likes_stats['missing_username']}")
        print(f"Missing bios: {likes_stats['missing_bio']}")
        print(f"Missing screenshots: {likes_stats['missing_screenshots']}")

        # Following analysis
        following = result['following']
        print("\nFollowing:")
        print(f"Total following: {len(following)}")
        print(f"Missing names: {sum(1 for f in following if not f['following_name'])}")
        print(f"Missing bios: {sum(1 for f in following if not f['following_bio'])}")

        # Followers analysis
        followers = result['followers']
        print("\nFollowers:")
        print(f"Total followers: {len(followers)}")
        print(f"Missing names: {sum(1 for f in followers if not f['follower_name'])}")
        print(f"Missing bios: {sum(1 for f in followers if not f['follower_bio'])}")

        # Content samples
        if tweets:
            print_header("Tweet Samples")
            for i, tweet in enumerate(tweets[:2], 1):
                print(f"\nTweet {i}:")
                print(f"Content: {tweet['tweet_content'][:150]}...")
                if 'quoted_content' in tweet:
                    print(f"Quote: {tweet['quoted_content'][:100]}...")

        if retweets:
            print_header("Retweet Samples")
            for i, rt in enumerate(retweets[:2], 1):
                print(f"\nRetweet {i}:")
                print(f"From: {rt['retweet_username']}")
                print(f"Content: {rt['retweet_main_content'][:150]}...")

        if likes:
            print_header("Like Samples")
            for i, like in enumerate(likes[:2], 1):
                print(f"\nLike {i}:")
                print(f"From: {like['liked_tweet_username']}")
                print(f"Content: {like['liked_tweet_content'][:150]}...")

        # Save analysis
        analysis = {
            'timestamp': timestamp,
            'stats': {
                'tweets': {
                    'total': len(tweets),
                    'empty': sum(1 for t in tweets if not t['tweet_content']),
                    'with_quotes': sum(1 for t in tweets if 'quoted_content' in t)
                },
                'retweets': retweet_stats,
                'likes': likes_stats,
                'following': {
                    'total': len(following),
                    'missing_names': sum(1 for f in following if not f['following_name']),
                    'missing_bios': sum(1 for f in following if not f['following_bio'])
                },
                'followers': {
                    'total': len(followers),
                    'missing_names': sum(1 for f in followers if not f['follower_name']),
                    'missing_bios': sum(1 for f in followers if not f['follower_bio'])
                }
            }
        }
        save_json(analysis, os.path.join(test_dir, "analysis.json"))

        print_header("Test Complete")
        print(f"Full results saved in: {test_dir}")
        return result

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return None

async def main():
    while True:
        print("\nTwitter Scraper Tester")
        print("1. Test profile")
        print("2. Exit")
        
        choice = input("\nChoice (1-2): ").strip()
        
        if choice == "1":
            username = input("Enter Twitter username (without @): ").strip()
            await test_profile(username)
            input("\nPress Enter to continue...")
        elif choice == "2":
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    asyncio.run(main()) 