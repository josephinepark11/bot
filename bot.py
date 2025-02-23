import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))  # Your Discord ID

COMMAND_PREFIX = '.'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

SETTINGS_FILE = 'server_settings.json'
ITEMS_FILE = "items.dat"
server_settings = {}

# ------------------------- Load & Save Settings -------------------------

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}  
    return {}

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(server_settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

@bot.event
async def on_ready():
    global server_settings
    print(f'Bot is ready! Logged in as {bot.user}')
    server_settings.update(load_settings())

# OWNER-ONLY CHECK
def is_owner(ctx):
    return ctx.author.id == BOT_OWNER_ID

# ------------------------- Setup Command (OWNER ONLY) -------------------------

class SetupModal(Modal):
    def __init__(self, setting_name: str):
        super().__init__(title=f"Setup {setting_name.upper()}")
        self.setting_name = setting_name
        self.add_item(TextInput(label="Enter the message:", style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        if guild_id not in server_settings:
            server_settings[guild_id] = {}

        server_settings[guild_id][self.setting_name] = self.children[0].value
        save_settings()

        await interaction.followup.send(f"✅ {self.setting_name.upper()} has been set up! Use `.{self.setting_name}` to view it.", ephemeral=True)

class SetupDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="GCASH PAYMENT"),
            discord.SelectOption(label="CPS PAYMENT"),
            discord.SelectOption(label="RGT PAYMENT"),
            discord.SelectOption(label="HOW TO GET UID"),
            discord.SelectOption(label="RGTRATE"),
            discord.SelectOption(label="GCASHRATE"),
            discord.SelectOption(label="BINANCERATE"),
        ]
        super().__init__(placeholder="Choose an option to set up", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetupModal(self.values[0].lower()))

class SetupView(View):
    def __init__(self):
        super().__init__()
        self.add_item(SetupDropdown())

@bot.tree.command(name="setup", description="Set up messages for commands (OWNER ONLY)")
async def setup(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=True)
        return
    await interaction.response.send_message("Select an option to set up:", view=SetupView(), ephemeral=True)

# ------------------------- Owner-Only Commands -------------------------

async def display_command(ctx, command_name: str):
    if not is_owner(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return
    
    guild_id = str(ctx.guild.id)
    message = server_settings.get(guild_id, {}).get(command_name)
    if message:
        await ctx.send(message)
    else:
        await ctx.send(f"No {command_name.upper()} message has been set. Use `/setup` to set it up.")

commands_list = {
    "rgt": "rgt", "uid": "uid", "gcash": "gcash", 
    "rategt": "rgtrate", "rgcash": "rgcash", "rbin": "binancerate"
}

for cmd, setting in commands_list.items():
    async def command_func(ctx, command_name=setting):
        await display_command(ctx, command_name)
    command_func.__name__ = f"display_{cmd}"
    bot.command(name=cmd)(commands.check(is_owner)(command_func))

# ------------------------- ID Search Command (Public) -------------------------

def search_items(keyword):
    """Search for items in the items.dat file by matching names."""
    if not os.path.exists(ITEMS_FILE):
        return []

    try:
        results = []
        current_id = None
        current_name = None
        
        with open(ITEMS_FILE, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                
                if line.startswith('Item ID: '):
                    current_id = int(line.split(': ')[1])
                elif line.startswith('Name: '):
                    current_name = line.split(': ')[1]
                    # If we have both ID and name, check if it matches search
                    if current_id is not None and keyword.lower() in current_name.lower():
                        seed_id = current_id + 1
                        results.append(f"{current_name} = `{current_id}` (Seed ID: `{seed_id}`)")
                    # Reset for next item
                    current_id = None
                    current_name = None

        return results
    except Exception as e:
        print(f"Error reading file: {e}")
        return []
    
class PaginationView(View):
    def __init__(self, results, keyword, author, per_page=10):
        super().__init__(timeout=60)
        self.results = results
        self.keyword = keyword
        self.author = author
        self.per_page = per_page
        self.current_page = 0

        self.prev_button = Button(label="◀", style=discord.ButtonStyle.grey)
        self.next_button = Button(label="▶", style=discord.ButtonStyle.grey)

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

        embed = discord.Embed(title=f"🔍 Results for '{self.keyword}'", color=discord.Color.blue())
        embed.description = "\n".join(f"{i+1}. {item}" for i, item in enumerate(page_results, start=start_idx + 1))

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

bot.run(TOKEN)
