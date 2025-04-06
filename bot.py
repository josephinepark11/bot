import discord
from discord.ext import commands
from discord import app_commands
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import aiohttp

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# LibreTranslate endpoint - using public instance (no API key required)
LIBRETRANSLATE_URL = "https://libretranslate.de/translate"

COMMAND_PREFIX = '.'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

ITEMS_FILE = "items.dat"

# ------------------------- Bot Initialization -------------------------

@bot.event
async def on_ready():
    print(f'✅ Bot is ready! Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} application commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ------------------------- ID Search Command (.id) -------------------------

def search_items(keyword):
    if not os.path.exists(ITEMS_FILE):
        print("Error: items.dat file not found!")
        return []

    try:
        results = []
        with open(ITEMS_FILE, "r", encoding="utf-8") as file:
            data = file.read()

        raw_items = re.split(r"-{50,}", data)

        for item in raw_items:
            name_match = re.search(r"Name:\s*(.+)", item, re.IGNORECASE)
            id_match = re.search(r"Item ID:\s*(\d+)", item, re.IGNORECASE)

            if name_match and id_match:
                name = name_match.group(1).strip()
                item_id = int(id_match.group(1).strip())

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
            title=f"🔍 Results for '{self.keyword}'",
            color=discord.Color.blue()
        )

        embed.description = "\n".join(f"{start_idx + idx + 1}. {item}" for idx, item in enumerate(page_results))
        total_pages = (len(self.results) - 1) // self.per_page + 1
        timestamp = datetime.now().strftime("%I:%M %p")

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
    
    # Send only one message with the embed and view
    await ctx.send(embed=embed, view=view)

# ------------------------- Translation Functions -------------------------

async def detect_language(text):
    """Detect language using LibreTranslate API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://libretranslate.de/detect",
                json={"q": text[:100]}  # Use just first 100 chars for detection
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        return data[0]["language"]
                return "en"  # Default to English if detection fails
    except Exception as e:
        print(f"Language detection error: {e}")
        return "en"  # Default to English on error

async def translate_text(text):
    """Translate text to English using LibreTranslate API without API key"""
    if not text:
        return "❌ No text provided for translation."
    
    try:
        # First detect the source language
        source_lang = await detect_language(text)
        
        # If already in English, no need to translate
        if source_lang == "en":
            return text
        
        payload = {
            "q": text,
            "source": source_lang,
            "target": "en"  # Always translate to English
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(LIBRETRANSLATE_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if "translatedText" in data:
                        return data["translatedText"]
                    return "❌ Translation response format unexpected."
                else:
                    error_text = await response.text()
                    print(f"Translation error: Status {response.status}, {error_text}")
                    return f"❌ Translation API returned status {response.status}"
    except aiohttp.ClientError as e:
        print(f"HTTP error during translation: {e}")
        return f"❌ Connection error: {str(e)}"
    except Exception as e:
        print(f"Unexpected translation error: {e}")
        return f"❌ Unexpected error: {str(e)}"

# ------------------------- Translate Commands -------------------------

@bot.tree.command(name="translate", description="Translate text to English")
@app_commands.describe(text="The text you want to translate")
async def translate_command(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=False)
    
    translated = await translate_text(text)
    
    # Simple format with no GUI elements
    response = f"<a:indo:1213790198123470848> original: {text}\n<a:flag_eng:1356665824257249332> english: {translated}"
    await interaction.followup.send(response)

@bot.tree.context_menu(name="Translate to English")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    if not message.content:
        await interaction.response.send_message("❌ That message has no text to translate.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=False)
    translated = await translate_text(message.content)
    
    # Simple format with no GUI elements
    response = f"original: {message.content}\nenglish: {translated}"
    await interaction.followup.send(response)

# ------------------------- Run the Bot -------------------------

bot.run(TOKEN)
