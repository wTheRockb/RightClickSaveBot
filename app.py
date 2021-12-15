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
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()


SEARCH_URL = "https://opensea.io/assets?search[categories][0]=art&search[sortAscending]=false&search[sortBy]=FAVORITE_COUNT&search[toggles][0]=IS_NEW"
BASE_ASSET_URL = "https://opensea.io"
ETH_PRICE_URI = "https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD"
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


def scrape_caption_and_save_file(db_conn): 
    with db_cur as db_conn.cursor():
        with webdriver.Chrome(
            ChromeDriverManager().install(),
            desired_capabilities=caps,
            options=chrome_options,
        ) as driver:
            driver.get(SEARCH_URL)
            items = driver.find_elements_by_class_name(".Asset--anchor")
            print("items found: ")
            for i in items:
                print(i.get_attribute("href"))
                nft_id = get_id_from_url(i.get_attribute("href"))
                if(!check_if_in_db(db_cur, nft_id)):
                    download_image_in_element(i)
                    nft_name artist_name, price = get_artist_and_price_from_element(i)
                    post_to_twitter(db_cur, db_conn, nft_id, nft_name, artist_name, price)
                    exit()


def check_if_in_db(db_cur, nft_id):
    cursor.execute(
        """
        SELECT nft_id FROM tweets WHERE nft_id = %s
        """, nft_id)
    potential_tweet = cursor.fetchone()
    return potential_tweet


def download_image_in_element(element):
    img = element.find_element_by_class_name("Image--image")
    src = img.get_attribute('src')
    urllib.urlretrieve(src, DOWNLOADED_IMAGE_URL)


def get_nft_info_from_element(element):
    elems = element.find_elements_by_class_name("Overflowreact__OverflowContainer-sc-10mm0lu-0 gjwKJf")
    artist_name = elems[0].get_attribute("inner_text")
    eth_price = elems[1].get_attribute("inner_text") # double check this only grabs the text and not the span inside
    nft_name = element.find_element_by_class_name("AssetCardFooter--name")[0].get_attribute("inner_text")
    return nft_name, artist_name, convert_from_eth_to_usd(eth_price)


def get_id_from_url(url):
    return url.split("matic/")[1]


def save_nft_as_tweeted(db_cur, db_conn, nft_id, nft_name, artist_name, price, tweet_url):
    cursor.execute(
        """
        INSERT INTO tweets (nft_id, nft_name, artist_name, price, tweet_url, occurred_at) VALUES
        (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, [nft_id, nft_name, artist_name, price, tweet_url])
    db_conn.commit()
    

def post_to_twitter(db_cur, db_conn, nft_id, nft_name, artist_name, price):
    caption_text = format_twitter_caption(nft_name, artist_name, price)
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
    #tweet_url = ...
    save_nft_as_tweeted(db_cur, db_conn, nft_id, nft_name, artist_name, price, tweet_url)


def format_twitter_caption(nft_name, artist_name, price):
    return f"""
    Title: {nft_name}
    Collection: {artist_name}
    Amount of money saved by viewing this tweet: ${price}
    """


def init_db_conn():
    return psycopg2.connect(user=os.environ['DB_USER'],
                                  password=os.environ['DB_PASSWORD'],
                                  host=os.environ['DB_HOST'],
                                  port=5432,
                                  database=os.environ['DB_NAME'])


def convert_from_eth_to_usd(ether):
    r = requests.get(ETH_PRICE_URI)
    data = r.json()
    eth_price = data["USD"]
    return ether * eth_price


if __name__ == "__main__":
    main()
