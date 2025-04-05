import discord
from discord.ext import commands
from discord import app_commands
import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv

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
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ------------------------- ID Search Command (.id) -------------------------

def search_items(keyword):
    if not os.path.exists(ITEMS_FILE):
        print("Error: items.dat file not found!")
        return []

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
        message = self.create_text()
        self.update_buttons()
        await interaction.response.edit_message(content=message, view=self)

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

    def create_text(self):
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_results = self.results[start_idx:end_idx]
        numbered = "\n".join(f"{start_idx + i + 1}. {item}" for i, item in enumerate(page_results))
        total_pages = (len(self.results) - 1) // self.per_page + 1
        return f"🔍 **Results for '{self.keyword}':**\n\n{numbered}\n\nPage {self.current_page+1}/{total_pages}"

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
    message = view.create_text()
    await ctx.send(content=message, view=view)

# ------------------------- Translation (LibreTranslate) -------------------------

def libre_translate(text: str, target_lang="en"):
    try:
        response = requests.post("https://libretranslate.com/translate", data={
            "q": text,
            "source": "auto",
            "target": target_lang,
            "format": "text"
        })
        response.raise_for_status()
        return response.json()["translatedText"]
    except Exception as e:
        print(f"Translation error: {e}")
        return None

@bot.tree.command(name="translate", description="Translate a message to English")
@app_commands.describe(message="Reply to a message to translate it")
async def translate_command(interaction: discord.Interaction, message: discord.Message = None):
    reference = interaction.message.reference if hasattr(interaction, 'message') and hasattr(interaction.message, 'reference') else None
    message_to_translate = message

    if not message and reference:
        try:
            message_to_translate = await interaction.channel.fetch_message(reference.message_id)
        except discord.NotFound:
            await interaction.response.send_message("❌ Referenced message not found.", ephemeral=True)
            return

    if not message_to_translate or not message_to_translate.content:
        await interaction.response.send_message("❌ The message has no text content to translate.", ephemeral=True)
        return

    translated = libre_translate(message_to_translate.content)
    if translated:
        await interaction.response.send_message(f"**Translated:** {translated}")
    else:
        await interaction.response.send_message("❌ Failed to translate the message.", ephemeral=True)

@bot.tree.context_menu(name="Translate to English")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    if not message.content:
        await interaction.response.send_message("❌ The message has no text content to translate.", ephemeral=True)
        return

    translated = libre_translate(message.content)
    if translated:
        await interaction.response.send_message(f"**Translated:** {translated}")
    else:
        await interaction.response.send_message("❌ Failed to translate the message.", ephemeral=True)

# ------------------------- Run the Bot -------------------------
bot.run(TOKEN)
