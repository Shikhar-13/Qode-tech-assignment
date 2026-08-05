# from scraper.parser import extract_tweet
# from scraper.utils import save_json, human_scroll

# import os
# from getpass import getpass
# from datetime import datetime, timedelta
# from urllib.parse import quote

# import undetected_chromedriver as uc

# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC


# TARGET_TWEETS = 2000
# SAVE_EVERY = 100


# def scrape():

#     USERNAME = os.getenv("X_USERNAME") or input("Username / Email: ")
#     PASSWORD = os.getenv("X_PASSWORD") or getpass("Password: ")

#     options = uc.ChromeOptions()

#     # options.add_argument("--headless=new")

#     options.add_argument("--start-maximized")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--window-size=1920,1080")

#     driver = uc.Chrome(
#         version_main=150,
#         options=options,
#         use_subprocess=True
#     )

#     wait = WebDriverWait(driver, 30)

#     # -----------------------------
#     # Login
#     # -----------------------------

#     driver.get("https://x.com")

#     username_box = wait.until(
#         EC.visibility_of_element_located(
#             (By.ID, "jf-input-username_or_email")
#         )
#     )

#     username_box.send_keys(USERNAME)
#     username_box.send_keys(Keys.ENTER)

#     password_box = wait.until(
#         EC.visibility_of_element_located(
#             (By.CSS_SELECTOR, "input[type='password']")
#         )
#     )

#     password_box.send_keys(PASSWORD)
#     password_box.send_keys(Keys.ENTER)

#     wait.until(
#         EC.any_of(
#             EC.url_contains("/home"),
#             EC.url_contains("/explore")
#         )
#     )

#     print("Logged in")

#     # -----------------------------
#     # Search
#     # -----------------------------

#     yesterday = (
#         datetime.utcnow() - timedelta(days=1)
#     ).strftime("%Y-%m-%d")

#     query = (
#         "(#nifty50 OR #sensex OR "
#         "#intraday OR #banknifty) "
#         f"since:{yesterday}"
#     )

#     search_url = (
#         f"https://x.com/search?q={quote(query)}&f=live"
#     )

#     driver.get(search_url)

#     wait.until(
#         EC.presence_of_element_located(
#             (
#                 By.CSS_SELECTOR,
#                 'article[data-testid="tweet"]'
#             )
#         )
#     )

#     print("Tweets loaded")

#     # -----------------------------
#     # Collect Tweets
#     # -----------------------------

#     all_tweets = []
#     seen = set()

#     scroll = 0

#     while len(all_tweets) < TARGET_TWEETS:

#         articles = driver.find_elements(
#             By.CSS_SELECTOR,
#             'article[data-testid="tweet"]'
#         )

#         print(
#             f"Scroll {scroll} | "
#             f"Visible {len(articles)}"
#         )

#         for article in articles:

#             tweet = extract_tweet(article)

#             tweet_id = tweet.get("tweet_id")

#             if not tweet_id:
#                 continue

#             if tweet_id in seen:
#                 continue

#             seen.add(tweet_id)

#             all_tweets.append(tweet)

#             print(
#                 f"[{len(all_tweets)}] "
#                 f"{tweet['username']}"
#             )

#             if len(all_tweets) % SAVE_EVERY == 0:

#                 save_json(
#                     "data/tweets.json",
#                     all_tweets
#                 )

#                 print(
#                     f"Saved {len(all_tweets)} tweets"
#                 )

#         human_scroll(driver)

#         scroll += 1

#     output_file = "data/raw/tweets.json"

#     save_json(
#         output_file,
#         all_tweets
#     )

#     driver.quit()

#     return output_file

from scraper.parser import extract_tweets
from scraper.utils import (
    save_json,
    human_scroll,
    build_search_url,
)

import os
from getpass import getpass
from datetime import datetime, timedelta

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


TARGET_TWEETS = 2000
SAVE_EVERY = 100
PARSE_EVERY_SCROLLS = 3


def scrape():

    USERNAME = os.getenv("X_USERNAME") or input("Username / Email: ")
    PASSWORD = os.getenv("X_PASSWORD") or getpass("Password: ")

    options = uc.ChromeOptions()

    # options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = uc.Chrome(
        version_main=150,
        options=options,
        use_subprocess=True
    )

    wait = WebDriverWait(driver, 30)

    # -------------------------------------------------------
    # Login
    # -------------------------------------------------------

    driver.get("https://x.com")

    username_box = wait.until(
        EC.visibility_of_element_located(
            (By.ID, "jf-input-username_or_email")
        )
    )

    username_box.clear()
    username_box.send_keys(USERNAME)
    username_box.send_keys(Keys.ENTER)

    password_box = wait.until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "input[type='password']")
        )
    )

    password_box.clear()
    password_box.send_keys(PASSWORD)
    password_box.send_keys(Keys.ENTER)

    wait.until(
        EC.any_of(
            EC.url_contains("/home"),
            EC.url_contains("/explore")
        )
    )

    print("✅ Logged in")

    # -------------------------------------------------------
    # Search
    # -------------------------------------------------------

    yesterday = (
        datetime.utcnow() - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    query = (
        "(#nifty50 OR #sensex OR "
        "#intraday OR #banknifty) "
        f"since:{yesterday}"
    )

    driver.get(build_search_url(query))

    wait.until(
        EC.presence_of_element_located(
            (
                By.CSS_SELECTOR,
                'article[data-testid="tweet"]'
            )
        )
    )

    print("✅ Tweets Loaded")

    # -------------------------------------------------------
    # Collection
    # -------------------------------------------------------

    all_tweets = []
    seen = set()

    scroll = 0

    while len(all_tweets) < TARGET_TWEETS:

        human_scroll(driver)

        scroll += 1

        if scroll % PARSE_EVERY_SCROLLS != 0:
            continue

        print(f"\nScroll {scroll}")

        timeline = driver.find_element(
            By.TAG_NAME,
            "main"
        )

        html = timeline.get_attribute("innerHTML")

        soup = BeautifulSoup(
            html,
            "lxml"
        )

        tweets = extract_tweets(soup)

        print(
            f"Parsed {len(tweets)} tweets"
        )

        new_count = 0

        for tweet in tweets:

            tweet_id = tweet.get("tweet_id")

            if not tweet_id:
                continue

            if tweet_id in seen:
                continue

            seen.add(tweet_id)

            all_tweets.append(tweet)

            new_count += 1

            print(
                f"[{len(all_tweets)}] "
                f"{tweet['username']}"
            )

            if len(all_tweets) % SAVE_EVERY == 0:

                save_json(
                    "data/raw/tweets.json",
                    all_tweets
                )

                print(
                    f"Checkpoint: {len(all_tweets)} tweets saved."
                )

            if len(all_tweets) >= TARGET_TWEETS:
                break

        print(
            f"New Tweets : {new_count}"
        )

    # -------------------------------------------------------
    # Save
    # -------------------------------------------------------

    output_file = "data/raw/tweets.json"

    save_json(
        output_file,
        all_tweets
    )

    print(
        f"\nFinished scraping {len(all_tweets)} tweets."
    )

    driver.quit()

    return output_file