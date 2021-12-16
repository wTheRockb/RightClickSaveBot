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

SEARCH_URL = "https://opensea.io/assets?search[categories][0]=art&search[sortAscending]=false&search[sortBy]=FAVORITE_COUNT&search[toggles][0]=IS_NEW"
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
# chrome_options.add_argument("--headless")
chrome_options.add_argument('--no-sandbox')


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
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Asset--anchor")))
            items = driver.find_elements(By.CLASS_NAME, "Asset--anchor")
            print("items found: ")
            print(items)
            for i in items:
                print(i.get_attribute("href"))
                nft_id = get_id_from_url(i.get_attribute("href"))
                print(f"nft_id: {nft_id}")
                if not check_if_in_db(db_cur, nft_id):
                    download_image_in_element(i)
                    nft_name, artist_name, price = get_nft_info_from_element(i)
                    print(nft_name)
                    print(artist_name)
                    print(price)
                    post_to_twitter(db_cur, db_conn, nft_id, nft_name, artist_name, price)
                    exit()


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
    artist_name = element.find_element(By.CSS_SELECTOR, ".gjwKJf").get_attribute("innerText")
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
    # Status(_api=<tweepy.api.API object at 0x7f3071e1c160>, _json={'created_at': 'Thu Dec 16 08:13:04 +0000 2021', 'id': 1471392922666864641, 'id_str': '1471392922666864641', 'text': 'Title: CryptoPunk #1961\n    Collection: JasseeNFT Labs\n    $ saved by viewing this tweet: $402.12 https://t.co/H1OB1q7d7B', 'truncated': False, 'entities': {'hashtags': [], 'symbols': [], 'user_mentions': [], 'urls': [], 'media': [{'id': 1471392918317371393, 'id_str': '1471392918317371393', 'indices': [98, 121], 'media_url': 'http://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'media_url_https': 'https://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'url': 'https://t.co/H1OB1q7d7B', 'display_url': 'pic.twitter.com/H1OB1q7d7B', 'expanded_url': 'https://twitter.com/RClickSaveBot/status/1471392922666864641/photo/1', 'type': 'photo', 'sizes': {'thumb': {'w': 150, 'h': 150, 'resize': 'crop'}, 'large': {'w': 276, 'h': 276, 'resize': 'fit'}, 'small': {'w': 276, 'h': 276, 'resize': 'fit'}, 'medium': {'w': 276, 'h': 276, 'resize': 'fit'}}}]}, 'extended_entities': {'media': [{'id': 1471392918317371393, 'id_str': '1471392918317371393', 'indices': [98, 121], 'media_url': 'http://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'media_url_https': 'https://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'url': 'https://t.co/H1OB1q7d7B', 'display_url': 'pic.twitter.com/H1OB1q7d7B', 'expanded_url': 'https://twitter.com/RClickSaveBot/status/1471392922666864641/photo/1', 'type': 'animated_gif', 'sizes': {'thumb': {'w': 150, 'h': 150, 'resize': 'crop'}, 'large': {'w': 276, 'h': 276, 'resize': 'fit'}, 'small': {'w': 276, 'h': 276, 'resize': 'fit'}, 'medium': {'w': 276, 'h': 276, 'resize': 'fit'}}, 'video_info': {'aspect_ratio': [1, 1], 'variants': [{'bitrate': 0, 'content_type': 'video/mp4', 'url': 'https://video.twimg.com/tweet_video/FGtwED1VEAEhww4.mp4'}]}}]}, 'source': '<a href="https://google.com" rel="nofollow">rightclicksavebot2</a>', 'in_reply_to_status_id': None, 'in_reply_to_status_id_str': None, 'in_reply_to_user_id': None, 'in_reply_to_user_id_str': None, 'in_reply_to_screen_name': None, 'user': {'id': 1457585966047121408, 'id_str': '1457585966047121408', 'name': 'RightClickSaveBot', 'screen_name': 'RClickSaveBot', 'location': '', 'description': 'Giving away thousands of dollars every hour', 'url': None, 'entities': {'description': {'urls': []}}, 'protected': False, 'followers_count': 0, 'friends_count': 1, 'listed_count': 0, 'created_at': 'Mon Nov 08 05:49:27 +0000 2021', 'favourites_count': 0, 'utc_offset': None, 'time_zone': None, 'geo_enabled': False, 'verified': False, 'statuses_count': 1, 'lang': None, 'contributors_enabled': False, 'is_translator': False, 'is_translation_enabled': False, 'profile_background_color': 'F5F8FA', 'profile_background_image_url': None, 'profile_background_image_url_https': None, 'profile_background_tile': False, 'profile_image_url': 'http://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', 'profile_image_url_https': 'https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', 'profile_link_color': '1DA1F2', 'profile_sidebar_border_color': 'C0DEED', 'profile_sidebar_fill_color': 'DDEEF6', 'profile_text_color': '333333', 'profile_use_background_image': True, 'has_extended_profile': True, 'default_profile': True, 'default_profile_image': True, 'following': False, 'follow_request_sent': False, 'notifications': False, 'translator_type': 'none', 'withheld_in_countries': []}, 'geo': None, 'coordinates': None, 'place': None, 'contributors': None, 'is_quote_status': False, 'retweet_count': 0, 'favorite_count': 0, 'favorited': False, 'retweeted': False, 'possibly_sensitive': False, 'lang': 'en'}, created_at=datetime.datetime(2021, 12, 16, 8, 13, 4, tzinfo=datetime.timezone.utc), id=1471392922666864641, id_str='1471392922666864641', text='Title: CryptoPunk #1961\n    Collection: JasseeNFT Labs\n    $ saved by viewing this tweet: $402.12 https://t.co/H1OB1q7d7B', truncated=False, entities={'hashtags': [], 'symbols': [], 'user_mentions': [], 'urls': [], 'media': [{'id': 1471392918317371393, 'id_str': '1471392918317371393', 'indices': [98, 121], 'media_url': 'http://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'media_url_https': 'https://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'url': 'https://t.co/H1OB1q7d7B', 'display_url': 'pic.twitter.com/H1OB1q7d7B', 'expanded_url': 'https://twitter.com/RClickSaveBot/status/1471392922666864641/photo/1', 'type': 'photo', 'sizes': {'thumb': {'w': 150, 'h': 150, 'resize': 'crop'}, 'large': {'w': 276, 'h': 276, 'resize': 'fit'}, 'small': {'w': 276, 'h': 276, 'resize': 'fit'}, 'medium': {'w': 276, 'h': 276, 'resize': 'fit'}}}]}, extended_entities={'media': [{'id': 1471392918317371393, 'id_str': '1471392918317371393', 'indices': [98, 121], 'media_url': 'http://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'media_url_https': 'https://pbs.twimg.com/tweet_video_thumb/FGtwED1VEAEhww4.jpg', 'url': 'https://t.co/H1OB1q7d7B', 'display_url': 'pic.twitter.com/H1OB1q7d7B', 'expanded_url': 'https://twitter.com/RClickSaveBot/status/1471392922666864641/photo/1', 'type': 'animated_gif', 'sizes': {'thumb': {'w': 150, 'h': 150, 'resize': 'crop'}, 'large': {'w': 276, 'h': 276, 'resize': 'fit'}, 'small': {'w': 276, 'h': 276, 'resize': 'fit'}, 'medium': {'w': 276, 'h': 276, 'resize': 'fit'}}, 'video_info': {'aspect_ratio': [1, 1], 'variants': [{'bitrate': 0, 'content_type': 'video/mp4', 'url': 'https://video.twimg.com/tweet_video/FGtwED1VEAEhww4.mp4'}]}}]}, source='rightclicksavebot2', source_url='https://google.com', in_reply_to_status_id=None, in_reply_to_status_id_str=None, in_reply_to_user_id=None, in_reply_to_user_id_str=None, in_reply_to_screen_name=None, author=User(_api=<tweepy.api.API object at 0x7f3071e1c160>, _json={'id': 1457585966047121408, 'id_str': '1457585966047121408', 'name': 'RightClickSaveBot', 'screen_name': 'RClickSaveBot', 'location': '', 'description': 'Giving away thousands of dollars every hour', 'url': None, 'entities': {'description': {'urls': []}}, 'protected': False, 'followers_count': 0, 'friends_count': 1, 'listed_count': 0, 'created_at': 'Mon Nov 08 05:49:27 +0000 2021', 'favourites_count': 0, 'utc_offset': None, 'time_zone': None, 'geo_enabled': False, 'verified': False, 'statuses_count': 1, 'lang': None, 'contributors_enabled': False, 'is_translator': False, 'is_translation_enabled': False, 'profile_background_color': 'F5F8FA', 'profile_background_image_url': None, 'profile_background_image_url_https': None, 'profile_background_tile': False, 'profile_image_url': 'http://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', 'profile_image_url_https': 'https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', 'profile_link_color': '1DA1F2', 'profile_sidebar_border_color': 'C0DEED', 'profile_sidebar_fill_color': 'DDEEF6', 'profile_text_color': '333333', 'profile_use_background_image': True, 'has_extended_profile': True, 'default_profile': True, 'default_profile_image': True, 'following': False, 'follow_request_sent': False, 'notifications': False, 'translator_type': 'none', 'withheld_in_countries': []}, id=1457585966047121408, id_str='1457585966047121408', name='RightClickSaveBot', screen_name='RClickSaveBot', location='', description='Giving away thousands of dollars every hour', url=None, entities={'description': {'urls': []}}, protected=False, followers_count=0, friends_count=1, listed_count=0, created_at=datetime.datetime(2021, 11, 8, 5, 49, 27, tzinfo=datetime.timezone.utc), favourites_count=0, utc_offset=None, time_zone=None, geo_enabled=False, verified=False, statuses_count=1, lang=None, contributors_enabled=False, is_translator=False, is_translation_enabled=False, profile_background_color='F5F8FA', profile_background_image_url=None, profile_background_image_url_https=None, profile_background_tile=False, profile_image_url='http://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', profile_image_url_https='https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', profile_link_color='1DA1F2', profile_sidebar_border_color='C0DEED', profile_sidebar_fill_color='DDEEF6', profile_text_color='333333', profile_use_background_image=True, has_extended_profile=True, default_profile=True, default_profile_image=True, following=False, follow_request_sent=False, notifications=False, translator_type='none', withheld_in_countries=[]), user=User(_api=<tweepy.api.API object at 0x7f3071e1c160>, _json={'id': 1457585966047121408, 'id_str': '1457585966047121408', 'name': 'RightClickSaveBot', 'screen_name': 'RClickSaveBot', 'location': '', 'description': 'Giving away thousands of dollars every hour', 'url': None, 'entities': {'description': {'urls': []}}, 'protected': False, 'followers_count': 0, 'friends_count': 1, 'listed_count': 0, 'created_at': 'Mon Nov 08 05:49:27 +0000 2021', 'favourites_count': 0, 'utc_offset': None, 'time_zone': None, 'geo_enabled': False, 'verified': False, 'statuses_count': 1, 'lang': None, 'contributors_enabled': False, 'is_translator': False, 'is_translation_enabled': False, 'profile_background_color': 'F5F8FA', 'profile_background_image_url': None, 'profile_background_image_url_https': None, 'profile_background_tile': False, 'profile_image_url': 'http://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', 'profile_image_url_https': 'https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', 'profile_link_color': '1DA1F2', 'profile_sidebar_border_color': 'C0DEED', 'profile_sidebar_fill_color': 'DDEEF6', 'profile_text_color': '333333', 'profile_use_background_image': True, 'has_extended_profile': True, 'default_profile': True, 'default_profile_image': True, 'following': False, 'follow_request_sent': False, 'notifications': False, 'translator_type': 'none', 'withheld_in_countries': []}, id=1457585966047121408, id_str='1457585966047121408', name='RightClickSaveBot', screen_name='RClickSaveBot', location='', description='Giving away thousands of dollars every hour', url=None, entities={'description': {'urls': []}}, protected=False, followers_count=0, friends_count=1, listed_count=0, created_at=datetime.datetime(2021, 11, 8, 5, 49, 27, tzinfo=datetime.timezone.utc), favourites_count=0, utc_offset=None, time_zone=None, geo_enabled=False, verified=False, statuses_count=1, lang=None, contributors_enabled=False, is_translator=False, is_translation_enabled=False, profile_background_color='F5F8FA', profile_background_image_url=None, profile_background_image_url_https=None, profile_background_tile=False, profile_image_url='http://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', profile_image_url_https='https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png', profile_link_color='1DA1F2', profile_sidebar_border_color='C0DEED', profile_sidebar_fill_color='DDEEF6', profile_text_color='333333', profile_use_background_image=True, has_extended_profile=True, default_profile=True, default_profile_image=True, following=False, follow_request_sent=False, notifications=False, translator_type='none', withheld_in_countries=[]), geo=None, coordinates=None, place=None, contributors=None, is_quote_status=False, retweet_count=0, favorite_count=0, favorited=False, retweeted=False, possibly_sensitive=False, lang='en')
    #
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
