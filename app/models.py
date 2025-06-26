from pydantic import BaseModel
from typing import List

class UserProfile(BaseModel):
    username: str
    bio: str

class Tweet(BaseModel):
    tweet_content: str
    tweet_screenshot: str

class Follower(BaseModel):
    follower_name: str
    follower_bio: str

class Following(BaseModel):
    following_name: str
    following_bio: str

class TwitterScrapeResponse(BaseModel):
    user_profile: UserProfile
    tweets: List[Tweet]
    following: List[Following]
    followers: List[Follower] 