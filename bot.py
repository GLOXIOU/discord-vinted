import discord
import asyncio
import json
import importlib
from discord.ext import commands, tasks
from discord import app_commands
import config
import random
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PRICE_MARGIN = float(os.getenv("PRICE_MARGIN", 0.15))

vinted_auth = importlib.import_module("vinted_auth")

ARTICLES_FILE = "followed_articles.json"
FILTERS_FILE = "filters.json"
CHECK_INTERVAL = 120

def load_followed_articles():
    try:
        with open(ARTICLES_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_followed_articles():
    with open(ARTICLES_FILE, "w") as file:
        json.dump(followed_articles, file, indent=4)

def load_filters():
    try:
        with open(FILTERS_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_filters():
    with open(FILTERS_FILE, "w") as file:
        json.dump(filters, file, indent=4)

followed_articles = load_followed_articles()
filters = load_filters()
already_seen_ids = set()

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)

def is_admin(user: discord.User):
    for role in user.roles:
        if role.name.lower() == "admin":
            return True
    return False

@client.event
async def on_ready():
    print(f"Connect as {client.user.name}")
    await client.tree.sync()
    check_new_articles.start()

@client.tree.command(name="follow-keyword")
@app_commands.describe(keyword="Keyword to follow")
async def suivre_motcle(interaction: discord.Interaction, keyword: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    search_url = f"https://www.vinted.fr/vetements?search_text={keyword}&order=newest_first"
    entry = {"keyword": keyword, "url": search_url, "last_items": []}

    if entry in followed_articles:
        await interaction.response.send_message("This keyword is already followed.", ephemeral=True)
        return

    followed_articles.append(entry)
    save_followed_articles()
    await interaction.response.send_message(f"The keyword '{keyword}' is add.", ephemeral=True)

@client.tree.command(name="add-filter")
@app_commands.describe(keyword="Keyword to filtered", price="target price", channel="target lounge")
async def ajouter_filtre(interaction: discord.Interaction, keyword: str, price: float, channel: discord.TextChannel):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    if not followed_articles:
        await interaction.response.send_message("No keywords tracked.", ephemeral=True)
        return

    selected_entry = next((entry for entry in followed_articles if entry["keyword"] == keyword), None)

    if not selected_entry:
        await interaction.response.send_message(f"Keyword '{keyword}' not found.", ephemeral=True)
        return

    filter_entry = {
        "keyword": selected_entry["keyword"],
        "price": price,
        "channel_id": channel.id
    }

    filters.append(filter_entry)
    save_filters()

    await interaction.response.send_message(
        f"Filter added for '{selected_entry['keyword']}' in <#{channel.id}> around {price} EUR.",
        ephemeral=True
    )

@client.tree.command(name="delete-keyword")
async def supprimer_motcle(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be an administrator.", ephemeral=True)
        return

    options = [discord.SelectOption(label=entry["keyword"], value=str(index)) for index, entry in enumerate(followed_articles)]

    select_menu = discord.ui.Select(placeholder="Choose a keyword", options=options)

    async def select_callback(interaction: discord.Interaction):
        selected_index = int(select_menu.values[0])
        entry_to_remove = followed_articles[selected_index]
        followed_articles.remove(entry_to_remove)
        save_followed_articles()
        await interaction.response.send_message(f"Keyword '{entry_to_remove['keyword']}' deletes.", ephemeral=True)

    select_menu.callback = select_callback
    view = discord.ui.View()
    view.add_item(select_menu)

    await interaction.response.send_message("Select a keyword to delete:", view=view)

@client.tree.command(name="list-keyword")
async def lister_motcles(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be an administrator.", ephemeral=True)
        return

    if not followed_articles:
        await interaction.response.send_message("No keywords tracked.", ephemeral=True)
        return

    embed = discord.Embed(title="Tracked keywords", color=discord.Color.blue())
    for entry in followed_articles:
        embed.add_field(
            name=f"{entry['keyword']}",
            value=f"URL: {entry['url']}\nMemorable Articles: {len(entry['last_items'])}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_new_articles():
    print("New check of the articles.")

    cookies = await vinted_auth.get_cookies()
    if not cookies:
        print("Error: Vinted cookies unavailable.")
        return

    for entry in followed_articles:
        try:
            max_retries = 2
            retry_count = 0
            items = None

            while retry_count <= max_retries:
                items = await vinted_auth.fetch_items_with_cookies(cookies, entry["url"])

                if isinstance(items, dict) and items.get("code") == 100:
                    print(f"401 detected - reloading cookies (attempt {retry_count+1})")
                    cookies = await vinted_auth.get_cookies()
                    retry_count += 1
                    await asyncio.sleep(1)
                    continue

                if isinstance(items, dict) and items.get("code") == 403:
                    print(f"403 Detected - User-Agent Change (Attempt {retry_count+1})")
                    cookies = await vinted_auth.get_cookies()
                    new_user_agent = vinted_auth.get_random_user_agent()
                    items = await vinted_auth.fetch_items_with_cookies_and_user_agent(cookies, entry["url"], new_user_agent)
                    retry_count += 1
                    await asyncio.sleep(1)
                    continue

                break

            if not items or (isinstance(items, dict) and items.get("code")):
                print(f"Complete failure for '{entry['keyword']}'")
                continue

            await asyncio.sleep(random.uniform(1.0, 2.5))

            for item in items:
                if item["url"] not in already_seen_ids:
                    already_seen_ids.add(item["url"])

                    full_url = f"https://www.vinted.fr{item['url']}" if not item['url'].startswith('https://') else item['url']
                    price_amount = float(item['price']['amount'])
                    currency_code = item['price']['currency_code']

                    matched = False
                    for filter_entry in filters:
                        if filter_entry["keyword"] == entry["keyword"]:
                            price_target = filter_entry["price"]
                            lower_bound = price_target * (1 - PRICE_MARGIN)
                            upper_bound = price_target * (1 + PRICE_MARGIN)
                            if not (lower_bound <= price_amount <= upper_bound):
                                continue

                            embed = discord.Embed(
                                title=item['title'],
                                url=full_url,
                                description=f"**💰 Price: {price_amount} {currency_code}**",
                                color=discord.Color.blue()
                            )
                            embed.set_image(url=item['photo']['url'])

                            channel = client.get_channel(filter_entry["channel_id"])
                            if channel:
                                await channel.send(embed=embed)
                                print(f"Article sent: {item['title']}")
                            else:
                                print(f"Error: Room not found for filter {filter_entry}")
                            matched = True
                    if not matched:
                        print(f"No filters match the item: {item['title']}")

        except Exception as e:
            print(f"Error during article loop: {e}")

client.run(TOKEN)