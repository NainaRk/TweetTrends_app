import configparser
import os
from random import randint
from time import sleep
from twikit import Client, TooManyRequests
import asyncio
import re
from datetime import datetime
import csv
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from flask import Flask, request, render_template

# Configuration
MINIMUM_TWEETS = 100

# Function to clean tweet text
def clean_text(text):
    text = re.sub(r"http\S+|www\S+|https\S+", '', text, flags=re.MULTILINE)  # Remove URLs
    text = re.sub(r"@\w+|#", '', text)  # Remove mentions and hashtags
    text = re.sub(r"[^\w\s]", '', text)  # Remove special characters
    text = re.sub(r"\s+", ' ', text).strip()  # Remove extra whitespace
    return text

# Function to analyze sentiment
def analyze_sentiment(text):
    analyzer = SentimentIntensityAnalyzer()
    score = analyzer.polarity_scores(text)['compound']
    if score > 0.05:
        return 'Positive'
    elif score < -0.05:
        return 'Negative'
    else:
        return 'Neutral'

# Function to clean and analyze tweets
def process_pipeline(input_file, output_file):
    print("Processing tweets for sentiment analysis...")
    df = pd.read_csv(input_file, encoding='utf-8')
    df['Text'] = df['Text'].apply(clean_text)  # Replace original text with cleaned text
    df['Sentiment'] = df['Text'].apply(analyze_sentiment)
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"Pipeline complete. Processed data saved to {output_file}")

# Scrape tweets function
async def scrape_tweets(query, output_file):
    print("Scraping tweets...")
    config = configparser.ConfigParser()
    config.read('config.ini')
    username = config['X']['username']
    email = config['X']['email']
    password = config['X']['password']
    client = Client(language='en-US')
    #await client.login(auth_info_1=username, auth_info_2=email, password=password)
    #client.save_cookies('cookies.json') 
    client.load_cookies('cookies.json')

    tweet_count = 0
    tweets = None

    with open(output_file, 'w', encoding="utf-8", newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Tweet_Count', 'UserName', 'Text', 'Created_At', 'Retweets', 'Likes', 'View_Count', 'HashTags', 'Tweet_Link'])

        while tweet_count < MINIMUM_TWEETS:
            try:
                if tweets is None:
                    tweets = await client.search_tweet(query, product='Top')
                else:
                    sleep(randint(10, 15))
                    tweets = await tweets.next()
            except TooManyRequests as e:
                rate_limit_reset = datetime.fromtimestamp(e.rate_limit_reset)
                sleep((rate_limit_reset - datetime.now()).total_seconds())
                continue

            if not tweets:
                break

            for tweet in tweets:
                hashtags = re.findall(r"#\w+", tweet.text)
                tweet_link = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}"
                writer.writerow([
                    tweet_count + 1,
                    tweet.user.name,
                    tweet.text,
                    tweet.created_at,
                    tweet.retweet_count,
                    tweet.favorite_count,
                    tweet.view_count,
                    hashtags,
                    tweet_link
                ])
                tweet_count += 1

    print("Scraping complete.")

# Main function
async def main(query):
    tweet_file = 'tweets.csv'
    processed_file = 'tweets_processed.csv'

    # Step 1: Scrape tweets
    await scrape_tweets(query, tweet_file)

    # Step 2: Process tweets (cleaning + sentiment analysis)
    process_pipeline(tweet_file, processed_file)

# Flask application
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    asyncio.run(main(query))
    df = pd.read_csv('tweets_processed.csv')
    positive_percent = round((df['Sentiment'] == 'Positive').mean() * 100)
    negative_percent = round((df['Sentiment'] == 'Negative').mean() * 100)
    top_positive = df[df['Sentiment'] == 'Positive'].nlargest(5, ['Retweets', 'Likes'])
    top_negative = df[df['Sentiment'] == 'Negative'].nlargest(5, ['Retweets', 'Likes'])
    return render_template('results.html', query=query, positive_percent=positive_percent, negative_percent=negative_percent, top_positive=top_positive, top_negative=top_negative)

if __name__ == '__main__':
    #app.run(debug=True)
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
