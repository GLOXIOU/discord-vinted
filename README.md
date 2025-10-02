# Vinted Discord Bot

A Discord bot that monitors Vinted for new items matching your keywords and sends notifications to specific channels.

⚠️ **Important notes**

* This bot only works on private servers and networks. Running it on a VPS is not supported.
* Excessive requests may result in an IP ban from the Vinted API. Use responsibly.

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/GLOXIOU/vinted-discord-bot.git
   cd vinted-discord-bot
   ```

2. Create a `.env` file with your configuration:

   ```
   DISCORD_TOKEN=your_discord_token
   PRICE_MARGIN=0.15
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Install Chromium (required for some Cloudflare bypasses / browser scripts):
   ```bash
   sudo apt-get update && sudo apt-get install -y chromium-browser
   ```

   Note: Depending on your distribution, the package may be named chromium instead of chromium-browser. If the above command doesn't work, try:
   ```bash
   sudo apt-get update && sudo apt-get install -y chromium
   ```

5. On your Discord server, create a role named **Admin** and assign it to users who should be able to use the bot commands.

6. Start the bot:

   ```bash
   python bot.py
   ```

---

## Commands

* `/add-filter` → Add a filter for a keyword (send messages to a channel when items match keyword and price).
* `/list-keyword` → List all tracked keywords.
* `/follow-keyword` → Start tracking a keyword (1 request every 2 minutes to Vinted).
* `/delete-keyword` → Remove a tracked keyword.

⚠️ You must have the **Admin** discord role to execute commands.

---

## How It Works

* **bot.py** → Main file that runs the bot.
* **.env** → Stores configuration values (token, margin, etc.).
* **filters.json** → References channels where notifications will be sent.
* **followed_articles.json** → Stores tracked articles.
* **vinted_auth.py** → Handles authentication and API requests to Vinted.
* **vinted_bypass.py** → Refreshes cookies and bypasses Cloudflare protection.

---

## Regional Notice

This bot was originally developed for **Vinted France (.fr)**.
If you are in another region, you must update all API links in the code accordingly.

## Disclaimer

This project is intended **for educational and personal use only**.

* This bot interacts with Vinted through **unofficial methods** (private API and automated requests).
* Using it extensively may lead to **IP bans, account restrictions, or breaking changes** if Vinted updates their platform.
* The author does **not provide any warranty** and is **not responsible** for misuse of this software.
* By using this project, you agree to take full responsibility for any consequences that may occur.


If you wish to use this bot, please do so **responsibly and at your own risk**.

