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

# Authentication for v1.1 API for media upload
auth = tweepy.OAuth1UserHandler(
    consumer_key=client_id,
    consumer_secret=client_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)
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

def fetch_fact_with_anthropic(person, max_length=150):
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
            "content": f"Tell me some interesting tid-bits about {person} in around {max_length} characters. Separate the tib-bits into paragraphs with around 60 words. Consider each paragraph as a single tweet in a thread of tweets. In the first paragraph, use pronouns to refer to this person, not name. Use appropriate symbols at end of each paragraph along with thread number showing that it is part of a thread. There should be at least 3 paragraphs and maximum of 5. Design the whole text in a way so that it will be enjoyable to read as a tweet. At the end of the first paragraph, add the hash tags #BornToday #OnThisDay and the most appropriate hash tag with the name of the person. Please note that only the first 280 characters will be visible on the Twitter timeline, so the first 280 characters should attract other users to engage in the tweet. Also include relevant hashtags in between to get more reach.",
        }
    ],
    model="claude-3-7-sonnet-20250219",
    )
    print(f"Anthropic response: {message.content}")
    return message.content[0].text

def create_tweet(birth_info, person):
    max_facts_length = 4000
    facts_text = fetch_fact_with_anthropic(person, max_facts_length)
    # Split the text into paragraphs (split on empty lines)
    paragraphs = facts_text.strip().split("\n\n")
    # Remove any empty strings from the list (if any)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    paragraphs[0] = f"{birth_info}\n\n{paragraphs[0]}"
    return paragraphs

def tweet_birth_with_image(retries):
    print("Getting Wiki info...")
    
    retries += 1
    if retries > 5:
        print("Retry limit exceeded.")
        return
    
    birth_info, image_url, person = get_notable_birth()

    if birth_info and image_url and person:
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
                return tweet_birth_with_image(retries)

            try:
                tweet_texts = create_tweet(birth_info, person)
                # Get your own user ID (needed to exclude mentions)
                me = client.get_me(user_fields=["id"])
                user_id = me.data.id
                previous_tweet_id = None
                for i, text in enumerate(tweet_texts):
                    response = client.create_tweet(
                        text=text,
                        in_reply_to_tweet_id=previous_tweet_id,
                        exclude_reply_user_ids=[user_id],  # Prevents @mention
                        media_ids=media_ids if i == 0 else None
                    )
                    
                    # Update previous_tweet_id for the next iteration
                    previous_tweet_id = response.data["id"]
                print("Tweet posted.")
            except tweepy.errors.TweepError as e:
                print(f"Error posting tweet: {e}")
        else:
            print("Failed to download image. Retrying with another person.")
            return tweet_birth_with_image(retries)
    else:
        print("No suitable birth information found. Retrying...")
        return tweet_birth_with_image(retries)

def main():
    retries = 0
    tweet_birth_with_image(retries)
    # test_tweet_birth_with_image()

# def test_tweet_birth_with_image():
#     birth_info, image_url, person = get_notable_birth()
#     if birth_info and image_url and person:
#         tweet_texts = create_tweet(birth_info, person)
#         print("Would tweet:\n")
#         for i, text in enumerate(tweet_texts):
#             print(f"{text}\n")
#         print(f"Image URL: {image_url}")
#     else:
#         print("No birth information found for today.")

if __name__ == "__main__":
    main()
