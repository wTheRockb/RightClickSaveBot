import tweepy
from bs4 import BeautifulSoup
import requests
from requests_oauthlib import OAuth1Session
import json
import os
from requests_html import HTML
from requests_html import HTMLSession
from dotenv import load_dotenv
import psycopg2

load_dotenv()


SEARCH_URL = "https://opensea.io/assets?search[categories][0]=art&search[sortAscending]=false&search[" \
             "sortBy]=FAVORITE_COUNT"
BASE_ASSET_URL = "https://opensea.io"
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
DOWNLOADED_IMAGE_URL = "current_nft"
consumer_key = os.environ.get("API_KEY")
consumer_secret = os.environ.get("API_SECRET")

def main():
    db_conn = init_db_conn()
    scrape_caption_and_save_file()
    #post_to_twitter("1635907876084.jpg", "this is a test! hello world!")

def scrape_caption_and_save_file(db_conn):
    db_cur = db_conn.cursor()
    html = requests.get(SEARCH_URL, headers=HEADERS)
    # print(html)
    html = HTML(html=html.text)
    html.render()
    # page = requests.get(SEARCH_URL, headers=HEADERS)
    # soup = BeautifulSoup(page.content, 'html.parser')
    print(html.links)
    print(html.absolute_links)
    grid_cells = html.find(".Asset--anchor")
    print(len(grid_cells))
    for cell in grid_cells:
        
        # if(!check_if_in_db(db_cur, X))

        exit()

def check_if_in_db(db_cur, nft_id):
    cursor.execute(
        """
        SELECT nft_id FROM tweets WHERE nft_id = %s
        """, nft_id)
    potential_tweet = cursor.fetchone()
    return potential_tweet

def save_nft_as_tweeted(db_cur, db_conn, nft_id, tweet_url):
    cursor.execute(
        """
        INSERT INTO tweets (nft_id, occurred_at, tweet_url) VALUES
        (%s, CURRENT_TIMESTAMP, %s)
        """, [nft_id, tweet_url])
    db_conn.commit()
    

def post_to_twitter( caption_text):
    auth = tweepy.OAuthHandler(
        os.environ['API_KEY'],
        os.environ['API_SECRET']
    )
    auth.set_access_token(
        os.environ['ACCESS_TOKEN'],
        os.environ['ACCESS_SECRET']
    )
    api = tweepy.API(auth)

    # Upload image
    media = api.media_upload(DOWNLOADED_IMAGE_URL)

    # Post tweet with image
    tweet = caption_text
    post_result = api.update_status(status=tweet, media_ids=[media.media_id])
    print(post_result)


def init_db_conn():
    return psycopg2.connect(user=os.environ['DB_USER'],
                                  password=os.environ['DB_PASSWORD'],
                                  host=os.environ['DB_HOST'],
                                  port=5432,
                                  database=os.environ['DB_NAME'])


if __name__ == "__main__":
    main()
