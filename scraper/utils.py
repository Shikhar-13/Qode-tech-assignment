# import json
# import random
# import time


# def save_json(filename, tweets):

#     with open(
#         filename,
#         "w",
#         encoding="utf-8"
#     ) as f:

#         json.dump(
#             tweets,
#             f,
#             indent=2,
#             ensure_ascii=False
#         )


# def human_scroll(driver):

#     driver.execute_script(
#         "window.scrollBy(0, arguments[0]);",
#         random.randint(900, 1400)
#     )

#     time.sleep(random.uniform(1.8, 3.5))

import json
import random
import time
from urllib.parse import quote


def save_json(filename, tweets):
    """
    Save tweets to a JSON file.
    """
    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            tweets,
            f,
            indent=2,
            ensure_ascii=False
        )


def build_search_url(query):
    """
    Build X search URL.
    """
    return (
        f"https://x.com/search?q={quote(query)}"
        "&f=live"
    )


def random_delay(min_time=0.8, max_time=1.5):
    """
    Random delay to simulate human browsing.
    """
    time.sleep(
        random.uniform(
            min_time,
            max_time
        )
    )


def human_scroll(driver):
    """
    Scroll down a random distance.
    """

    pixels = random.randint(
        1500,
        2200
    )

    driver.execute_script(
        """
        window.scrollBy({
            top: arguments[0],
            behavior: 'smooth'
        });
        """,
        pixels
    )

    random_delay()


def wait_for_new_tweets(driver, previous_height):
    """
    Wait until additional tweets have loaded.
    Returns the new page height.
    """

    timeout = 10
    start = time.time()

    while time.time() - start < timeout:

        current_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        if current_height > previous_height:
            return current_height

        time.sleep(0.5)

    return previous_height