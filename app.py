import tweepy
import requests
import json
import os
from dotenv import load_dotenv
import psycopg2
from selenium.webdriver.common.by import By
import urllib.request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

SEARCH_URL = "https://opensea.io/assets?search[categories][0]=art&search[sortAscending]=false&search[sortBy]=FAVORITE_COUNT&search[toggles][0]=IS_NEW&search[toggles][1]=HAS_OFFERS"
BASE_ASSET_URL = "https://opensea.io"
ETH_PRICE_URI = "https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'}
DOWNLOADED_IMAGE_URL = "current_nft.png"
consumer_key = os.environ.get("API_KEY")
consumer_secret = os.environ.get("API_SECRET")
chrome_options = Options()
#chrome_options.add_argument("--headless")
chrome_options.add_argument('--no-sandbox')
ARTIST_NAME_SELECTOR = "jPSCbX"
FILE_SIZE_LIMIT = 5242880
DEBUG_MODE = False


def main():
    db_conn = init_db_conn()
    scrape_caption_and_save_file(db_conn)


def scrape_caption_and_save_file(db_conn):
    with db_conn.cursor() as db_cur:
        with webdriver.Chrome(
                ChromeDriverManager().install(),
                options=chrome_options,
        ) as driver:
            driver.set_window_size(1920, 1080)
            driver.get(SEARCH_URL)
            wait = WebDriverWait(driver, 10)
            if DEBUG_MODE: 
                driver.save_screenshot("screenshot.png")
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Asset--anchor")))
            items = driver.find_elements(By.CLASS_NAME, "Asset--anchor")
            for i in items:
                print(f"item href: {i.get_attribute('href')}")
                nft_id = get_id_from_url(i.get_attribute("href"))
                print(f"nft_id: {nft_id}")
                download_image_in_element(i)
                if nft_passes_checks(db_cur, nft_id):
                    nft_name, artist_name, price = get_nft_info_from_element(i)
                    print(f"nft_name: {nft_name}")
                    print(f"artist_name: {artist_name}")
                    print(f"price: {price}")
                    post_to_twitter(db_cur, db_conn, nft_id, nft_name, artist_name, price)
                    exit()


def nft_passes_checks(db_cur, nft_id):
    return  not check_if_in_db(db_cur, nft_id) and acceptable_file_size()


def acceptable_file_size():
    file_size = os.path.getsize(DOWNLOADED_IMAGE_URL)
    print(f"file_size of nft printed below: {file_size}")

    return file_size < FILE_SIZE_LIMIT

def check_if_in_db(db_cur, nft_id):
    db_cur.execute(
        """
        SELECT nft_id FROM tweets WHERE nft_id = %s
        """, [nft_id])
    potential_tweet = db_cur.fetchone()
    return potential_tweet


def download_image_in_element(element):
    img = element.find_element(By.CLASS_NAME, "Image--image")
    src = img.get_attribute('src')
    urllib.request.urlretrieve(src, DOWNLOADED_IMAGE_URL)


def get_nft_info_from_element(element):
    artist_name = element.find_element(By.CSS_SELECTOR, "." + ARTIST_NAME_SELECTOR).get_attribute("innerText")
    eth_price = element.find_element(By.CLASS_NAME, "Price--amount").get_attribute("innerText")
    nft_name = element.find_element(By.CLASS_NAME, "AssetCardFooter--name").get_attribute("innerText")
    return nft_name, artist_name, convert_from_eth_to_usd(eth_price)


def get_id_from_url(url):
    return url.split("assets/")[1]


def save_nft_as_tweeted(db_cur, db_conn, nft_id, nft_name, artist_name, price, tweet_url):
    db_cur.execute(
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
    # tweet_url = ...
    # save_nft_as_tweeted(db_cur, db_conn, nft_id, nft_name, artist_name, price, tweet_url)


def format_twitter_caption(nft_name, artist_name, price):
    return f"""
Title: {nft_name}
Collection: {artist_name}
$ Saved by viewing this tweet: ${price}
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
    # print(f"ether price: {eth_price}")
    # print(f"ether: {ether} {type(ether)}")
    if ether:
        return round(float(ether) * eth_price, 2)
    else:
        return -1


if __name__ == "__main__":
    main()
