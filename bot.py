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

    try:
        synced = await bot.tree.sync()  # Syncs slash commands globally
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ------------------------- /raypost Command (GUI Modal) -------------------------

class RaypostModal(Modal):
    def __init__(self):
        super().__init__(title="📢 Create a Raypost")
        self.description = TextInput(label="Enter the message:", style=discord.TextStyle.paragraph)
        self.gif_url = TextInput(label="Optional GIF URL (leave blank if none)", required=False)

        self.add_item(self.description)
        self.add_item(self.gif_url)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📢 Announcement",
            description=self.description.value,
            color=discord.Color.gold()
        )

        if self.gif_url.value.strip():  # If user provided a GIF URL
            embed.set_image(url=self.gif_url.value.strip())

        embed.set_footer(text=f"Posted by {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        await interaction.response.send_message("✅ Raypost sent!", ephemeral=True)
        await interaction.channel.send(embed=embed)

@bot.tree.command(name="raypost", description="Create a Raypost with a description and optional GIF.")
async def raypost(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=True)
        return
    await interaction.response.send_modal(RaypostModal())

# ------------------------- /setup Command (Dropdown) -------------------------

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

        await interaction.followup.send(f"✅ `{self.setting_name.upper()}` has been set! Use `.{self.setting_name}` to view it.", ephemeral=True)

class SetupDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="CPS", value="cps"),
            discord.SelectOption(label="GCASH", value="gcash"),
            discord.SelectOption(label="RGT", value="rgt"),
            discord.SelectOption(label="UID", value="uid"),
            discord.SelectOption(label="RGT-R", value="rgtrate"),
            discord.SelectOption(label="CPS-R", value="cpsrate"),
            discord.SelectOption(label="BINANCE-R", value="binancerate"),
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

def is_owner(ctx):
    return ctx.author.id == BOT_OWNER_ID

async def display_command(ctx, command_name: str):
    if not is_owner(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return
    
    guild_id = str(ctx.guild.id)
    message = server_settings.get(guild_id, {}).get(command_name)
    if message:
        await ctx.send(message)
    else:
        await ctx.send(f"No `{command_name.upper()}` message has been set. Use `/setup` to set it up.")

# Register commands dynamically
commands_list = {
    "cps": "cps", "gcash": "gcash", "rgt": "rgt", "uid": "uid",
    "rgtrate": "rgtrate", "cpsrate": "cpsrate", "binancerate": "binancerate"
}

for cmd, setting in commands_list.items():
    async def command_func(ctx, command_name=setting):
        await display_command(ctx, command_name)
    
    command_func.__name__ = f"display_{cmd}"
    bot.command(name=cmd)(commands.check(is_owner)(command_func))


# ------------------------- List Command -------------------------

@bot.command(name="list")
async def list_commands(ctx):
    embed = discord.Embed(title="📜 List of Commands", color=discord.Color.blue())
    embed.description = (
        "**Here are all the available `.commands` you can use:**\n"
        "**.cps** - CPS Payment Information\n"
        "**.gcash** - GCash Payment Details\n"
        "**.rgt** - RGT Payment Info\n"
        "**.uid** - How to Get UID\n"
        "**.rgtrate** - RGT Rate Information\n"
        "**.cpsrate** - CPS Rate Information\n"
        "**.binancerate** - Binance Rate Details\n\n"
        "Use `/setup` to configure these commands."
    )
    await ctx.send(embed=embed)

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

        # Properly split items
        raw_items = re.split(r"-{50,}", data)  # Splits at lines with 50+ dashes

        for item in raw_items:
            name_match = re.search(r"Name:\s*(.+)", item, re.IGNORECASE)
            id_match = re.search(r"Item ID:\s*(\d+)", item, re.IGNORECASE)

            if name_match and id_match:
                name = name_match.group(1).strip()
                item_id = int(id_match.group(1).strip())
                seed_name = f"{name} Seed"
                seed_id = item_id + 1  

                # Search for substring match
                if keyword.lower() in name.lower():
                    results.append(f"{name} - {item_id}")
                    results.append(f"{seed_name} - {seed_id}")

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

        embed = discord.Embed(
            title=f"🔍 **RESULTS FOR '{self.keyword.upper()}'**",  # BIGGER title
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

bot.run(TOKEN)
