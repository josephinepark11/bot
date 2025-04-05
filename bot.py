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
# Initialize the LibreTranslate API client
translator = LibreTranslateAPI("https://libretranslate.de")
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

# ------------------------- Translate Command -------------------------
@bot.tree.command(name="translate", description="Translate text to English")
@app_commands.describe(text="Text to translate")
async def translate_command(interaction: discord.Interaction, text: str = None):
    if not text:
        await interaction.response.send_message("❌ Please provide text to translate.", ephemeral=True)
        return
    
    try:
        # Translate text from any language to English
        translated = translator.translate(text, target_lang='en')
        
        # Send the translated message
        await interaction.response.send_message(f"Original: {text}\nTranslated: {translated}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

# ------------------------- Translate Context Menu -------------------------
@bot.tree.context_menu(name="Translate to English")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    if not message.content:
        await interaction.response.send_message("❌ The message has no text content to translate.", ephemeral=True)
        return
    
    try:
        # Translate the message from any language to English
        translated = translator.translate(message.content, target_lang='en')
        
        # Send the translated message
        await interaction.response.send_message(f"Original: {message.content}\nTranslated: {translated}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

# ------------------------- Run the Bot -------------------------
bot.run(TOKEN)
