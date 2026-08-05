# import re
# from selenium.webdriver.common.by import By


# def safe_text(article, by, selector):
#     try:
#         return article.find_element(by, selector).text
#     except Exception:
#         return ""


# def extract_metric(article, testid):
#     try:
#         btn = article.find_element(
#             By.CSS_SELECTOR,
#             f'[data-testid="{testid}"]'
#         )

#         label = btn.get_attribute("aria-label") or ""

#         m = re.search(r"(\d+)", label.replace(",", ""))

#         return int(m.group(1)) if m else 0

#     except Exception:
#         return 0


# def extract_views(article):
#     try:
#         analytics = article.find_element(
#             By.XPATH,
#             './/a[contains(@href,"analytics")]'
#         )

#         label = analytics.get_attribute("aria-label") or ""

#         m = re.search(r"(\d+)", label.replace(",", ""))

#         return int(m.group(1)) if m else 0

#     except Exception:
#         return 0


# def extract_tweet(article):

#     tweet = {}

#     try:
#         tweet["username"] = article.find_element(
#             By.XPATH,
#             './/div[@data-testid="User-Name"]//span[contains(text(),"@")]'
#         ).text
#     except Exception:
#         tweet["username"] = ""

#     try:
#         tweet["timestamp"] = article.find_element(
#             By.TAG_NAME,
#             "time"
#         ).get_attribute("datetime")
#     except Exception:
#         tweet["timestamp"] = ""

#     tweet["content"] = safe_text(
#         article,
#         By.CSS_SELECTOR,
#         '[data-testid="tweetText"]'
#     )

#     tweet["hashtags"] = re.findall(r"#\w+", tweet["content"])
#     tweet["mentions"] = re.findall(r"@\w+", tweet["content"])

#     tweet["engagement"] = {
#         "likes": extract_metric(article, "like"),
#         "replies": extract_metric(article, "reply"),
#         "retweets": extract_metric(article, "retweet"),
#         "views": extract_views(article)
#     }

#     try:
#         url = article.find_element(
#             By.XPATH,
#             './/a[contains(@href,"/status/")]'
#         ).get_attribute("href")

#         tweet["tweet_url"] = url
#         tweet["tweet_id"] = url.split("/")[-1]

#     except Exception:
#         tweet["tweet_url"] = ""
#         tweet["tweet_id"] = ""

#     return tweet
import re
from bs4 import BeautifulSoup


def safe_text(element):
    return element.get_text(" ", strip=True) if element else ""


def extract_metric(article, testid):
    """
    Extract likes, replies and retweets from aria-label.
    """

    btn = article.select_one(f'[data-testid="{testid}"]')

    if not btn:
        return 0

    label = btn.get("aria-label", "")

    match = re.search(r"([\d,.]+)", label)

    if not match:
        return 0

    return int(match.group(1).replace(",", ""))


def extract_views(article):
    """
    Extract views from analytics link.
    """

    analytics = article.select_one('a[href*="analytics"]')

    if not analytics:
        return 0

    label = analytics.get("aria-label", "")

    match = re.search(r"([\d,.]+)", label)

    if not match:
        return 0

    return int(match.group(1).replace(",", ""))


def extract_tweet(article):

    tweet = {}

    # ------------------------------------
    # Username
    # ------------------------------------

    username = ""

    user = article.select_one('div[data-testid="User-Name"]')

    if user:

        spans = user.find_all("span")

        for span in spans:

            text = span.get_text(strip=True)

            if text.startswith("@"):
                username = text
                break

    tweet["username"] = username

    # ------------------------------------
    # Timestamp
    # ------------------------------------

    time_tag = article.find("time")

    tweet["timestamp"] = (
        time_tag.get("datetime", "")
        if time_tag else ""
    )

    # ------------------------------------
    # Content
    # ------------------------------------

    content = article.select_one(
        '[data-testid="tweetText"]'
    )

    tweet["content"] = safe_text(content)

    # ------------------------------------
    # Hashtags / Mentions
    # ------------------------------------

    tweet["hashtags"] = re.findall(
        r"#\w+",
        tweet["content"]
    )

    tweet["mentions"] = re.findall(
        r"@\w+",
        tweet["content"]
    )

    # ------------------------------------
    # Engagement
    # ------------------------------------

    tweet["engagement"] = {

        "likes": extract_metric(
            article,
            "like"
        ),

        "replies": extract_metric(
            article,
            "reply"
        ),

        "retweets": extract_metric(
            article,
            "retweet"
        ),

        "views": extract_views(
            article
        )

    }

    # ------------------------------------
    # Tweet URL / Tweet ID
    # ------------------------------------

    tweet["tweet_url"] = ""
    tweet["tweet_id"] = ""

    links = article.find_all("a", href=True)

    for link in links:

        href = link["href"]

        if "/status/" in href:

            if href.startswith("/"):

                href = "https://x.com" + href

            tweet["tweet_url"] = href

            tweet["tweet_id"] = href.split("/")[-1].split("?")[0]

            break

    return tweet


def extract_tweets(soup):
    """
    Parse entire timeline and return all tweets.
    """

    tweets = []

    articles = soup.select(
        'article[data-testid="tweet"]'
    )

    for article in articles:

        try:
            tweet = extract_tweet(article)

            if tweet["tweet_id"]:
                tweets.append(tweet)

        except Exception:
            continue

    return tweets