import discord
import asyncio
import json
import importlib
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
from pathlib import Path
from dotenv import load_dotenv
from status_embed import StatusEmbed
from urllib.parse import quote

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("DISCORD_TOKEN")
PRICE_MARGIN = float(os.getenv("PRICE_MARGIN", 0.15))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL", "0"))

vinted_auth = importlib.import_module("vinted_auth")

ARTICLES_FILE = "followed_articles.json"
FILTERS_FILE = "filters.json"
CHECK_INTERVAL = 120

def load_followed_articles():
    try:
        with open(ARTICLES_FILE, "r") as file:
            return json.load(file)
    except:
        return []

def save_followed_articles():
    with open(ARTICLES_FILE, "w") as file:
        json.dump(followed_articles, file, indent=4)

def load_filters():
    try:
        with open(FILTERS_FILE, "r") as file:
            return json.load(file)
    except:
        return []

def save_filters():
    with open(FILTERS_FILE, "w") as file:
        json.dump(filters, file, indent=4)

followed_articles = load_followed_articles()
filters = load_filters()
already_seen_ids = set()
stats = {"found": 0, "sent": 0}
status_embed = None
sent_embeds = {}

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)

def is_admin(user: discord.User):
    return any(role.name.lower() == "admin" for role in getattr(user, "roles", []))

@client.event
async def on_ready():
    global status_embed
    print(f"Connected as {client.user.name}")
    await client.tree.sync()
    status_embed = StatusEmbed(client, CHECK_INTERVAL, followed_articles, stats, ADMIN_CHANNEL_ID)
    
    admin_channel = client.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        async for msg in admin_channel.history(limit=50):
            if msg.author == client.user:
                try:
                    await msg.delete()
                except:
                    pass
                break

    await status_embed.ensure_message()
    client.loop.create_task(status_embed.run_updater())
    check_new_articles.start()
    print("Bot is ready and running.")

@client.tree.command(name="follow-keyword")
@app_commands.describe(keyword="Keyword to follow")
async def follow_keyword(interaction: discord.Interaction, keyword: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be admin to use this command.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    search_url = f"https://www.vinted.fr/vetements?search_text={quote(keyword)}&order=newest_first"
    entry = {"keyword": keyword, "url": search_url}
    if any(e["keyword"] == keyword for e in followed_articles):
        await interaction.followup.send("This keyword is already followed.", ephemeral=True)
        return
    followed_articles.append(entry)
    save_followed_articles()
    await interaction.followup.send(f"Keyword '{keyword}' is now being tracked.", ephemeral=True)

class FilterModal(discord.ui.Modal):
    def __init__(self, keyword, channel):
        super().__init__(title=f"Add filter for {keyword}")
        self.keyword = keyword
        self.channel = channel
        self.price_input = discord.ui.TextInput(label="Target price", placeholder="Ex: 25.0")
        self.add_item(self.price_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            price = float(self.price_input.value)
        except ValueError:
            await interaction.response.send_message("Invalid price.", ephemeral=True)
            return
        filters.append({"keyword": self.keyword, "price": price, "channel_id": self.channel.id})
        save_filters()
        await interaction.response.send_message(f"Filter added for '{self.keyword}' in <#{self.channel.id}> at ~{price}€.", ephemeral=True)

@client.tree.command(name="add-filter")
async def add_filter(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be admin to use this command.", ephemeral=True)
        return
    if not followed_articles:
        await interaction.response.send_message("No tracked keywords.", ephemeral=True)
        return
    await interaction.response.send_message("Select a keyword for this filter:", ephemeral=True)
    keyword_options = [discord.SelectOption(label=e["keyword"], value=str(i)) for i, e in enumerate(followed_articles)]
    keyword_select = discord.ui.Select(placeholder="Choose keyword", options=keyword_options)
    async def keyword_callback(interaction: discord.Interaction):
        keyword_index = int(keyword_select.values[0])
        keyword = followed_articles[keyword_index]["keyword"]
        channels = [c for c in interaction.guild.text_channels if c.permissions_for(interaction.user).send_messages]
        channel_options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in channels]
        channel_select = discord.ui.Select(placeholder="Choose channel", options=channel_options)
        async def channel_callback(interaction: discord.Interaction):
            channel_id = int(channel_select.values[0])
            channel = client.get_channel(channel_id)
            modal = FilterModal(keyword, channel)
            await interaction.response.send_modal(modal)
        channel_select.callback = channel_callback
        view = discord.ui.View()
        view.add_item(channel_select)
        await interaction.response.send_message("Select a channel for this filter:", view=view, ephemeral=True)
    keyword_select.callback = keyword_callback
    view = discord.ui.View()
    view.add_item(keyword_select)
    await interaction.edit_original_response(view=view)

@client.tree.command(name="list-keywords")
async def list_keywords(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be admin to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not followed_articles:
        await interaction.followup.send("No tracked keywords.", ephemeral=True)
        return
    embed = discord.Embed(title="Tracked Keywords", color=discord.Color.blue())
    for entry in followed_articles:
        url = entry["url"]
        embed.add_field(name=entry["keyword"], value=f"[Link]({url})", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="list-filters")
async def list_filters(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be admin to use this command.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not filters:
        await interaction.followup.send("No filters set.", ephemeral=True)
        return
    embed = discord.Embed(title="Filters", color=discord.Color.blue())
    for f in filters:
        kw = f["keyword"]
        price = f["price"]
        ch = client.get_channel(f["channel_id"])
        ch_name = ch.mention if ch else "Channel not found"
        embed.add_field(name=kw, value=f"Price: ~{price}€, Channel: {ch_name}", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="delete-keyword")
async def delete_keyword(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be admin to use this command.", ephemeral=True)
        return
    options = [discord.SelectOption(label=e["keyword"], value=str(i)) for i, e in enumerate(followed_articles)]
    select_menu = discord.ui.Select(placeholder="Choose a keyword to delete", options=options)
    async def select_callback(interaction: discord.Interaction):
        index = int(select_menu.values[0])
        entry = followed_articles.pop(index)
        save_followed_articles()
        await interaction.response.send_message(f"Keyword '{entry['keyword']}' removed.", ephemeral=True)
    select_menu.callback = select_callback
    view = discord.ui.View()
    view.add_item(select_menu)
    await interaction.response.send_message("Select a keyword to delete:", view=view, ephemeral=True)

@client.tree.command(name="delete-filter")
async def delete_filter(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("You must be admin to use this command.", ephemeral=True)
        return
    options = [
        discord.SelectOption(
            label=f"{f['keyword']} → {client.get_channel(f['channel_id']).name if client.get_channel(f['channel_id']) else 'Unknown'} (~{f['price']}€)",
            value=str(i)
        ) for i, f in enumerate(filters)
    ]
    select_menu = discord.ui.Select(placeholder="Choose a filter to delete", options=options)
    async def select_callback(interaction: discord.Interaction):
        index = int(select_menu.values[0])
        entry = filters.pop(index)
        save_filters()
        await interaction.response.send_message(f"Filter for '{entry['keyword']}' removed.", ephemeral=True)
    select_menu.callback = select_callback
    view = discord.ui.View()
    view.add_item(select_menu)
    await interaction.response.send_message("Select a filter to delete:", view=view, ephemeral=True)

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_new_articles():
    global status_embed
    if status_embed:
        status_embed.reset_timer()
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
                    cookies = await vinted_auth.get_cookies()
                    retry_count += 1
                    await asyncio.sleep(1)
                    continue
                if isinstance(items, dict) and items.get("code") == 403:
                    cookies = await vinted_auth.get_cookies()
                    new_user_agent = vinted_auth.get_random_user_agent()
                    items = await vinted_auth.fetch_items_with_cookies_and_user_agent(cookies, entry["url"], new_user_agent)
                    retry_count += 1
                    await asyncio.sleep(1)
                    continue
                break
            if not items or (isinstance(items, dict) and items.get("code")):
                print(f"Failed for '{entry['keyword']}'")
                continue
            await asyncio.sleep(random.uniform(1.0, 2.5))
            for item in items:
                stats["found"] += 1
                item_url = item.get("url")
                if not item_url or item_url in already_seen_ids:
                    continue
                already_seen_ids.add(item_url)
                full_url = f"https://www.vinted.fr{item_url}" if not item_url.startswith("https://") else item_url
                price_obj = item.get('price') or {}
                price_amount = float(price_obj.get('amount', 0))
                currency_code = price_obj.get('currency_code', '')
                matched = False
                for filter_entry in filters:
                    if filter_entry["keyword"] != entry["keyword"]:
                        continue
                    price_target = filter_entry["price"]
                    lower_bound = price_target * (1 - PRICE_MARGIN)
                    upper_bound = price_target * (1 + PRICE_MARGIN)
                    if not (lower_bound <= price_amount <= upper_bound):
                        continue
                    embed = discord.Embed(
                        title=item.get('title', 'Untitled'),
                        url=full_url,
                        description=f"**💰 Price: {price_amount} {currency_code}**",
                        color=discord.Color.blue()
                    )
                    photos = item.get('photos', [])
                    if photos:
                        embed.set_image(url=photos[0])
                    embed.add_field(name="🏷️ Brand", value=item.get('brand', 'Unknown'), inline=True)
                    embed.add_field(name="📏 Size", value=item.get('size', 'Not specified'), inline=True)
                    embed.add_field(name="🧥 Condition", value=item.get('condition', 'Not specified'), inline=True)
                    if len(photos) > 1:
                        links = [f"[Photo {i+1}]({url})" for i, url in enumerate(photos[1:3])]
                        embed.add_field(name="📸 More Photos", value="\n".join(links), inline=False)
                    channel = client.get_channel(filter_entry["channel_id"])
                    if channel:
                        msg = await channel.send(embed=embed)
                        sent_embeds[item_url] = msg.id
                        stats["sent"] += 1
                    matched = True
        except Exception as e:
            print(f"Error in item loop: {e}")

client.run(TOKEN)