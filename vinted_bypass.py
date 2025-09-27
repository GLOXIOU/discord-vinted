import undetected_chromedriver as uc
import json
import time
import os
import requests

COOKIES_FILE = "cookies.json"
COOKIE_EXPIRY_FILE = "cookies_expire.txt"
COOKIE_LIFETIME_SECONDS = 30 * 60

def get_vinted_cookies():
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = uc.Chrome(options=options)
    print("[*] Access to Vinted to bypass Cloudflare...")
    driver.get("https://www.vinted.fr/")

    time.sleep(10)

    cookies = driver.get_cookies()
    driver.quit()

    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)

    with open(COOKIE_EXPIRY_FILE, "w") as f:
        f.write(str(int(time.time()) + COOKIE_LIFETIME_SECONDS))

    print("[*] Cookies updated and saved.")
    return cookies

def cookies_expired():
    if not os.path.exists(COOKIE_EXPIRY_FILE):
        return True
    try:
        with open(COOKIE_EXPIRY_FILE, "r") as f:
            expiry = int(f.read())
            return time.time() > expiry
    except:
        return True

def load_cookies():
    if not os.path.exists(COOKIES_FILE) or cookies_expired():
        return get_vinted_cookies()
    with open(COOKIES_FILE, "r") as f:
        return json.load(f)

def make_vinted_request(url, headers=None, retry=True):
    cookies = load_cookies()
    session = requests.Session()

    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])

    response = session.get(url, headers=headers)

    if response.status_code == 401 and retry:
        print("[!] Error 401: Invalid cookies. Attempting to refresh...")
        cookies = get_vinted_cookies()
        session.cookies.clear()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        response = session.get(url, headers=headers)

    return response