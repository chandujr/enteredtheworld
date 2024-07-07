import tweepy
import requests
from datetime import datetime
import time
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from io import BytesIO
import uuid

# TODO:
# 1. Tweet only if image is available [done]
# 2. Tweet 3 times a day: 0200, 1200, 2100
# 3. Use high quality image
# 4. If the randomly picked tweet has no image, pick again
# 5. Avoid repetition of persons on the same day

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

def get_notable_birth():
    # Use Pacific Time for the date
    today = datetime.now(ZoneInfo("America/Los_Angeles"))
    date = today.strftime("%m/%d")
    
    # Using the Wikipedia API to get events for the day
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/{date}"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"})
    data = response.json()
    
    if data and 'births' in data and len(data['births']) > 0:
        import random
        event = random.choice(data['births'])
        year = event['year']
        text = event['text']
        
        # Check for thumbnail in the API response
        thumbnail_url = None
        if 'pages' in event and event['pages']:
            page = event['pages'][0]
            if 'thumbnail' in page:
                thumbnail_url = page['thumbnail'].get('source')
        
        return f"On this day in {year}, {text} entered the world.", thumbnail_url
    return None, None

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
    print("Getting Wiki info...")
    birth_info, image_url = get_notable_birth()
    if birth_info:
        print(f"Got birth info: {birth_info}")
        print(f"Image URL: {image_url}")
        if image_url:
            media_ids = []
            image = download_image(image_url)
            if image:
                unique_filename = "temp.jpg"
                try:
                    # Save the image to a file
                    with open(unique_filename, 'wb') as f:
                        f.write(image.getvalue())
                    print(f"Temporary file saved at: {unique_filename}")
                    media = api.media_upload(filename=unique_filename)
                    media_ids.append(media.media_id)
                except Exception as e:
                    print(f"Error handling image: {e}. Cancelling tweet.")
                    return
                
                try:
                    response = client.create_tweet(text=birth_info, media_ids=media_ids)
                    print(f"Tweeted: {birth_info}")
                    if media_ids:
                        print("Tweet includes an image.")
                except tweepy.TweepError as e:
                    print(f"Error posting tweet: {e}")
            else:
                print("Failed to download image. Cancelling tweet.")
        else:
            print("No image found for the person. Cancelling tweet.")
    else:
        print("No birth information found for today. Cancelling tweet.")

def main():
    while True:
        # Use Pacific Time for checking the current time
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
        print(f"Minute is now {now.minute}.")
        if now.hour == 2 and now.minute == 0:  # 2:00 AM
            tweet_birth_with_image()
            time.sleep(60)  # Wait for a minute to avoid duplicate tweets
        time.sleep(30)  # Check every 30 seconds

        # Testing
        # if now.minute % 3 == 0:  # every 2 minutes
        #     tweet_birth_with_image()
        #     time.sleep(60)  # Wait for a minute to avoid duplicate tweets
        # time.sleep(30)  # Check every 30 seconds

def test_get_birth():
    birth_info, image_url = get_notable_birth()
    if birth_info:
        print(f"Would tweet: {birth_info} Image URL: {image_url}")
    else:
        print("No birth information found for today.")

if __name__ == "__main__":
    main()