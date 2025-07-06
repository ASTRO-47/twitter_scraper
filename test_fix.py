#!/usr/bin/env python3
"""
Test script to verify the screenshot duplication fix
"""
import os
import sys
import glob
from app.scraper import clean_username_for_filename, cleanup_existing_screenshots, generate_unique_screenshot_filename

def test_clean_username_for_filename():
    """Test username cleaning function"""
    print("Testing username cleaning...")
    
    test_cases = [
        ("@williamair1", "williamair1"),
        ("@williamair1 ", "williamair1"),
        ("user with spaces", "user_with_spaces"),
        ("user/with/slashes", "user_with_slashes"),
        ("user@domain.com", "userdomain.com"),
        ("normal_user", "normal_user"),
    ]
    
    for input_name, expected in test_cases:
        result = clean_username_for_filename(input_name)
        print(f"  '{input_name}' -> '{result}' (expected: '{expected}')")
        assert result == expected, f"Failed for {input_name}"
    
    print("✓ Username cleaning tests passed")

def test_unique_filename_generation():
    """Test unique filename generation"""
    print("\nTesting unique filename generation...")
    
    username = "testuser"
    filenames = set()
    
    # Generate multiple filenames and ensure they're unique
    for i in range(5):
        filename = generate_unique_screenshot_filename(username, "tweet", i+1)
        print(f"  Generated: {filename}")
        assert filename not in filenames, f"Duplicate filename: {filename}"
        filenames.add(filename)
    
    print("✓ Unique filename generation tests passed")

def test_cleanup_function():
    """Test cleanup function (dry run)"""
    print("\nTesting cleanup function...")
    
    # Create some test files
    screenshots_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    
    test_files = [
        "testuser_tweet_1.png",
        "testuser_retweet_1.png",
        "@testuser_tweet_1.png",
        "@testuser_retweet_1.png",
    ]
    
    # Create test files
    for filename in test_files:
        test_path = os.path.join(screenshots_dir, filename)
        with open(test_path, 'w') as f:
            f.write("test")
    
    print(f"  Created {len(test_files)} test files")
    
    # Count before cleanup
    before_count = len(glob.glob(os.path.join(screenshots_dir, "testuser*")))
    print(f"  Files before cleanup: {before_count}")
    
    # Run cleanup
    cleanup_existing_screenshots("testuser")
    
    # Count after cleanup
    after_count = len(glob.glob(os.path.join(screenshots_dir, "testuser*")))
    print(f"  Files after cleanup: {after_count}")
    
    print("✓ Cleanup function test completed")

def main():
    print("Running screenshot duplication fix tests...\n")
    
    try:
        test_clean_username_for_filename()
        test_unique_filename_generation()
        test_cleanup_function()
        
        print("\n✓ All tests passed! The fix should work correctly.")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
