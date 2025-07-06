from pydantic import BaseModel
from typing import List, Optional

class UserProfile(BaseModel):
    username: str
    bio: str

class Tweet(BaseModel):
    tweet_content: str
    tweet_screenshot: str

class Retweet(BaseModel):
    retweet_content: str
    retweet_username: str
    retweet_profile_bio: str
    retweet_screenshot: str
    retweet_main_content: str

class Like(BaseModel):
    liked_tweet_content: str
    liked_tweet_username: str
    liked_tweet_profile_bio: str
    liked_tweet_screenshot: str
    liked_main_content: str

class Follower(BaseModel):
    follower_name: str
    follower_bio: str

class Following(BaseModel):
    following_name: str
    following_bio: str

class TwitterScrapeResponse(BaseModel):
    user_profile: UserProfile
    tweets: List[Tweet]
    retweets: List[Retweet]
    likes: Optional[List[Like]] = []
    following: Optional[List[Following]] = []
    followers: Optional[List[Follower]] = [] 