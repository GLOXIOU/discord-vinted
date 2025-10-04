import discord
import asyncio
import datetime
import os

class StatusEmbed:
    def __init__(self, client, check_interval, followed_articles, stats, admin_channel_id):
        self.client = client
        self.check_interval = check_interval
        self.followed_articles = followed_articles
        self.stats = stats
        self.message = None
        self.start_time = datetime.datetime.utcnow()
        self.admin_channel_id = int(admin_channel_id) if str(admin_channel_id).isdigit() else 0
        self.last_check_time = datetime.datetime.utcnow()

    def uptime(self):
        delta = datetime.datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"

    def next_refresh(self):
        elapsed = (datetime.datetime.utcnow() - self.last_check_time).total_seconds()
        remaining = max(0, self.check_interval - int(elapsed))
        minutes, seconds = divmod(remaining, 60)
        return f"{minutes}m {seconds}s"

    def build_embed(self):
        keywords = [entry["keyword"] for entry in self.followed_articles]
        keyword_list = ", ".join(keywords) if keywords else "None"
        embed = discord.Embed(
            title="🔍 Vinted Bot Status",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="📌 Tracked Keywords", value=keyword_list, inline=False)
        embed.add_field(name="⏳ Next Refresh", value=self.next_refresh(), inline=True)
        embed.add_field(name="📦 Articles Found", value=str(self.stats["found"]), inline=True)
        embed.add_field(name="📤 Articles Sent", value=str(self.stats["sent"]), inline=True)
        embed.add_field(name="🕒 Uptime", value=self.uptime(), inline=False)
        return embed

    async def ensure_message(self):
        if not self.admin_channel_id:
            print("[StatusEmbed] ADMIN_CHANNEL_ID not set.")
            return
        channel = self.client.get_channel(self.admin_channel_id)
        if channel is None:
            print(f"[StatusEmbed] Channel not found: {self.admin_channel_id}")
            return
        if self.message is None:
            embed = self.build_embed()
            self.message = await channel.send(embed=embed)
            print("[StatusEmbed] Initial status embed sent.")
        else:
            await self.update()

    async def update(self):
        if self.message is None:
            return
        embed = self.build_embed()
        try:
            await self.message.edit(embed=embed)
        except Exception as e:
            print(f"[StatusEmbed] Update failed: {e}")
            self.message = None

    def reset_timer(self):
        self.last_check_time = datetime.datetime.utcnow()

    async def run_updater(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await self.ensure_message()
            await asyncio.sleep(1)