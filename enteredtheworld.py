import tweepy
import requests
from datetime import datetime
import time
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from io import BytesIO
import uuid
import random

# Load environment variables
load_dotenv()

# Twitter API credentials
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

# Authenticate with Twitter API v2
client = tweepy.Client(
    consumer_key=client_id,
    consumer_secret=client_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)

# We still need v1.1 API for media upload
auth = tweepy.OAuthHandler(client_id, client_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Global variable to store the people tweeted about today
tweeted_people = []

def get_notable_birth():
    global tweeted_people

    # Use Pacific Time for the date
    today = datetime.now(ZoneInfo("America/Los_Angeles"))
    date = today.strftime("%m/%d")
    
    # Using the Wikipedia API to get events for the day
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/{date}"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"})
    data = response.json()
    
    if data and 'births' in data:
        # Filter events to only include those with images
        events_with_images = [event for event in data['births'] if 'pages' in event and event['pages'] and 'originalimage' in event['pages'][0]]
        
        # Remove already tweeted people
        events_with_images = [event for event in events_with_images if event['text'] not in tweeted_people]
        
        if events_with_images:
            event = random.choice(events_with_images)
            year = event['year']
            text = event['text']
            
            # Get the original image URL
            image_url = event['pages'][0]['originalimage']['source']
            
            return f"On this day in {year}, {text} entered the world.\n\n#BornToday #OnThisDay", image_url, text
    return None, None, None

def download_image(url):
    print("Downloading image...")
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"})
    if response.status_code == 200:
        content_type = response.headers.get('content-type')
        print(f"Content-Type of the image: {content_type}")
        return BytesIO(response.content)
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
        return None

def tweet_birth_with_image():
    global tweeted_people

    print("Getting Wiki info...")
    birth_info, image_url, person = get_notable_birth()
    
    if birth_info and image_url:
        media_ids = []
        image = download_image(image_url)
        if image:
            fname = "temp.jpg"
            try:
                # Save the image to a file
                with open(fname, 'wb') as f:
                    f.write(image.getvalue())
                print(f"Temporary file saved at: {fname}")
                media = api.media_upload(filename=fname)
                media_ids.append(media.media_id)
            except Exception as e:
                print(f"Error handling image: {e}. Retrying with another person.")
                return tweet_birth_with_image()
            
            try:
                response = client.create_tweet(text=birth_info, media_ids=media_ids)
                print(f"Tweeted: {birth_info}")
                tweeted_people.append(person)
                print("Tweet includes an image.")
            except tweepy.TweepError as e:
                print(f"Error posting tweet: {e}")
        else:
            print("Failed to download image. Retrying with another person.")
            return tweet_birth_with_image()
    else:
        print("No suitable birth information found. Retrying...")
        return tweet_birth_with_image()

def main():
    global tweeted_people
    
    while True:
        # Use Pacific Time for checking the current time
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
        print(f"Hour is now {now.hour} and Minute is now {now.minute}.")
        if now.hour in [2, 12, 21] and now.minute == 0:  # 2:00 AM, 12:00 PM, 9:00 PM
            tweet_birth_with_image()
            time.sleep(60)  # Wait for a minute to avoid duplicate tweets
        
        # Reset tweeted_people at the start of a new day
        if now.hour == 0 and now.minute == 0:
            tweeted_people = []
        
        time.sleep(30)  # Check every 30 seconds

# def test_get_birth():
#     global tweeted_people

#     birth_info, image_url, person = get_notable_birth()
#     if birth_info:
#         print(f"Would tweet: {birth_info} Image URL: {image_url}")
#         tweeted_people.append(person)
#     else:
#         print("No birth information found for today.")

if __name__ == "__main__":
    main()