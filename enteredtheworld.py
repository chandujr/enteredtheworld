import tweepy
import requests
from datetime import datetime, date
import time
import os
from dotenv import load_dotenv
from io import BytesIO
import random
import json
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Twitter API credentials
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

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

def load_tweeted_people():
    try:
        with open('tweeted_people.json', 'r') as f:
            data = json.load(f)
            if data['date'] != date.today().isoformat():
                # It's a new day, reset the list
                return set()
            return set(data['people'])
    except FileNotFoundError:
        return set()

def save_tweeted_people(tweeted_people):
    with open('tweeted_people.json', 'w') as f:
        json.dump({
            'date': date.today().isoformat(),
            'people': list(tweeted_people)
        }, f)

def get_notable_birth():
    tweeted_people = load_tweeted_people()

    today = datetime.now()
    date = today.strftime("%m/%d")

    # Using the Wikipedia API to get events for the day
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/{date}"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"})
    data = response.json()

    if data and 'births' in data:
        # Filter events to only include those with images
        events_with_images = [event for event in data['births']
                              if 'pages' in event and event['pages']
                              and 'originalimage' in event['pages'][0]
                              and event['text'] not in tweeted_people]

        if events_with_images:
            event = random.choice(events_with_images)
            year = event['year']
            text = event['text']
            image_url = event['pages'][0]['originalimage']['source']

            tweeted_people.add(text)
            save_tweeted_people(tweeted_people)

            return f"On this day in {year}, {text} entered the world.", image_url, text
    return None, None, None

def download_image(url):
    print("Downloading image...")
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"})
    if response.status_code == 200:
        return BytesIO(response.content)
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
        return None

def fetch_fact_with_anthropic(text, max_length=150):
    client = Anthropic(
        api_key=anthropic_api_key
    )

    print(f"Fetching fact with {max_length} characters...")
    message = client.messages.create(
    max_tokens=1024,
    temperature=0.2,
    system="Respond only with the tid-bit.",
    messages=[
        {
            "role": "user",
            "content": f"Tell me the most interesting tid-bit about {text} in around {max_length} characters. Use pronouns to refer to this person, not name.",
        }
    ],
    model="claude-3-7-sonnet-20250219",
    )
    print(f"Anthropic response: {message.content}")
    return message.content[0].text

def create_tweet(birth_info, text):
    max_summary_length = 280 - len(birth_info) - len("\n\n\n\n#BornToday #OnThisDay")
    while True:
        summary = fetch_fact_with_anthropic(text, max_summary_length)
        tweet = f"{birth_info}\n\n{summary}\n\n#BornToday #OnThisDay"

        if len(tweet) <= 280:
            print("Generated fact is within 280 characters.")
            return tweet

        # If still too long, reduce max_summary_length and try again
        max_summary_length -= 10  # Reduce by 10 characters each iteration
        print(f"Tweet too long. Retrying fact gen with {max_summary_length} characters")

def tweet_birth_with_image():
    print("Getting Wiki info...")
    birth_info, image_url, text = get_notable_birth()

    if birth_info and image_url and text:
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
                tweet_text = create_tweet(birth_info, text)
                response = client.create_tweet(text=tweet_text, media_ids=media_ids)
                print(f"Tweeted: {tweet_text}")
                print("Tweet includes an image.")
            except tweepy.errors.TweepError as e:
                print(f"Error posting tweet: {e}")
        else:
            print("Failed to download image. Retrying with another person.")
            return tweet_birth_with_image()
    else:
        print("No suitable birth information found. Retrying...")
        return tweet_birth_with_image()

def main():
    tweet_birth_with_image()
    # test_tweet_birth_with_image()

# def test_tweet_birth_with_image():
#     birth_info, image_url, text = get_notable_birth()
#     if birth_info and image_url and text:
#         tweet_text = create_tweet(birth_info, text)
#         print(f"Would tweet: {tweet_text}")
#         print(f"Image URL: {image_url}")
#     else:
#         print("No birth information found for today.")

if __name__ == "__main__":
    main()
