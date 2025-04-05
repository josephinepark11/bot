import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import requests  # For making requests to LibreTranslate

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

COMMAND_PREFIX = '.'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

ITEMS_FILE = "items.dat"

# ------------------------- Bot Initialization -------------------------
@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')

    try:
        synced = await bot.tree.sync()  # Syncs slash commands globally
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ------------------------- ID Search Command (Public) -------------------------
def search_items(keyword):
    """Search for items in the items.dat file."""
    if not os.path.exists(ITEMS_FILE):
        print("Error: items.dat file not found!")
        return []

    try:
        results = []
        with open(ITEMS_FILE, "r", encoding="utf-8") as file:
            data = file.read()

        # Properly split items using 50+ dashes
        raw_items = re.split(r"-{50,}", data)

        for item in raw_items:
            name_match = re.search(r"Name:\s*(.+)", item, re.IGNORECASE)
            id_match = re.search(r"Item ID:\s*(\d+)", item, re.IGNORECASE)

            if name_match and id_match:
                name = name_match.group(1).strip()
                item_id = int(id_match.group(1).strip())

                # Check if the keyword matches the name
                if keyword.lower() in name.lower():
                    results.append(f"{name} - {item_id}")

        return results  
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

class PaginationView(discord.ui.View):
    def __init__(self, results, keyword, author, per_page=20):
        super().__init__(timeout=60)
        self.results = results
        self.keyword = keyword
        self.author = author
        self.per_page = per_page
        self.current_page = 0

        self.prev_button = discord.ui.Button(label="◀", style=discord.ButtonStyle.grey)
        self.next_button = discord.ui.Button(label="▶", style=discord.ButtonStyle.grey)

        self.prev_button.callback = self.previous_page
        self.next_button.callback = self.next_page

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = (self.current_page + 1) * self.per_page >= len(self.results)

    async def update_message(self, interaction):
        embed = self.create_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ You cannot control this pagination!", ephemeral=True)
        self.current_page -= 1
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ You cannot control this pagination!", ephemeral=True)
        self.current_page += 1
        await self.update_message(interaction)

    def create_embed(self):
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_results = self.results[start_idx:end_idx]

        embed = discord.Embed(
            title=f"🔍 **RESULTS FOR '{self.keyword.upper()}'**",
            color=discord.Color.blue()
        )

        # Make sure numbering starts at 1 per page (1-40, 41-80, etc.)
        embed.description = "\n".join(f"{start_idx + idx + 1}. {item}" for idx, item in enumerate(page_results))

        total_pages = (len(self.results) - 1) // self.per_page + 1
        timestamp = datetime.now().strftime("%I:%M %p")

        # Footer with user profile pic
        embed.set_footer(
            text=f"Requested by {self.author} | Page {self.current_page+1}/{total_pages} • Today at {timestamp}",
            icon_url=self.author.avatar.url if self.author.avatar else None
        )

        return embed

@bot.command(name="id")
async def search_item(ctx, *, item_name: str):
    if len(item_name) < 3:
        await ctx.send("❌ Please enter at least **3 characters** to search.")
        return

    results = search_items(item_name)
    if not results:
        await ctx.send(f"❌ No items found for '{item_name}'.")
        return

    view = PaginationView(results, item_name, ctx.author)
    embed = view.create_embed()
    await ctx.send(embed=embed, view=view)

# ------------------------- Translate Command using LibreTranslate -------------------------

# Function for translating using LibreTranslate
def translate_text(text, target_language="en"):
    try:
        url = "https://libretranslate.de/translate"  # LibreTranslate public API URL
        payload = {
            'q': text,
            'source': 'auto',  # Auto-detect the language
            'target': target_language,
            'format': 'text'
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        # Make the POST request
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()  # Raise an error if the request failed

        # Get the translated text
        translated_text = response.json()['translatedText']
        return translated_text
    except Exception as e:
        print(f"Error translating text: {e}")
        return None

# Slash Command to translate
@bot.tree.command(name="translate", description="Translate the message you're replying to")
async def translate_command(interaction: discord.Interaction):
    # Check if it's a reply
    if not interaction.message or not interaction.message.reference:
        await interaction.response.send_message("❌ Please reply to a message to translate it.", ephemeral=True)
        return

    # Try to fetch the replied-to message
    try:
        replied_message = await interaction.channel.fetch_message(interaction.message.reference.message_id)
    except:
        await interaction.response.send_message("❌ Failed to fetch the message you're replying to.", ephemeral=True)
        return

    if not replied_message.content:
        await interaction.response.send_message("❌ The replied message has no text.", ephemeral=True)
        return

    # Translate the message using LibreTranslate
    translated_text = translate_text(replied_message.content)

    if translated_text:
        await interaction.response.send_message(f"Translated Text: {translated_text}")
    else:
        await interaction.response.send_message("❌ Failed to translate the message.", ephemeral=True)

# ------------------------- Run the Bot -------------------------
bot.run(TOKEN)
