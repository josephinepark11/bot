import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from discord import ButtonStyle
from discord.ext.commands import has_permissions

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
TICKET_CHANNEL_ID = 1206254577851174923  # Replace with your actual ticket channel ID

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

# ------------------------- Owner-Only Commands (WITH EMBED GUI) -------------------------

async def display_command(ctx, command_name: str):
    if not is_owner(ctx):
        await ctx.send("❌ You are not authorized to use this command.")
        return
    
    guild_id = str(ctx.guild.id)
    message = server_settings.get(guild_id, {}).get(command_name)

    if message and message.strip():  # Ensure message is not empty
        embed = discord.Embed(description=message, color=discord.Color.random())
        embed.set_footer(text=f"Requested by {ctx.author}", 
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
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

        # Properly split items using 50+ dashes
        raw_items = re.split(r"-{50,}", data)

        for item in raw_items:
            name_match = re.search(r"Name:\s*(.+)", item, re.IGNORECASE)
            id_match = re.search(r"Item ID:\s*(\d+)", item, re.IGNORECASE)

            if name_match and id_match:
                name = name_match.group(1).strip()
                item_id = int(id_match.group(1).strip())

                # Check if the keyword matches either the item or its seed
                if keyword.lower() in name.lower():
                    results.append(f"{name} - {item_id}")

        return results  
    except Exception as e:
        print(f"Error reading file: {e}")
        return []


    
class PaginationView(View):
    def __init__(self, results, keyword, author, per_page=20):
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


# ------------------------- Ticket Panel Setup -------------------------

class TicketSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎟 Setup Ticket Panel")

        self.add_item(TextInput(label="Enter Ticket Description", required=True))
        self.add_item(TextInput(label="Optional GIF URL", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Ticket Support",
            description=self.children[0].value,
            color=discord.Color.blue()
        )
        if self.children[1].value:
            embed.set_image(url=self.children[1].value)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

        view = TicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel created!", ephemeral=True)

# ------------------------- Ticket Buttons -------------------------

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(Button(label="🛒 BUY SCRIPT", style=discord.ButtonStyle.green, custom_id="buy_script"))
        self.add_item(Button(label="💎 BUY BGL", style=discord.ButtonStyle.blurple, custom_id="buy_bgl"))
        self.add_item(Button(label="❓ HELP", style=discord.ButtonStyle.grey, custom_id="help_ticket"))

# ------------------------- Buy Script Modal -------------------------

class BuyScriptModal(Modal):
    def __init__(self):
        super().__init__(title="🛒 Buy Script")

        self.add_item(TextInput(label="What script do you want to buy?", required=True))
        self.add_item(TextInput(label="What is your UID?", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        script_name = self.children[0].value
        uid = self.children[1].value

        ticket_channel = await interaction.channel.create_thread(
            name=f"script-{interaction.user.name}",
            type=discord.ChannelType.public_thread
        )

        await ticket_channel.send(
            f"🔔 **New Script Request!**\n"
            f"👤 **User:** {interaction.user.mention}\n"
            f"📜 **Script:** `{script_name}`\n"
            f"🆔 **UID:** `{uid}`\n\n"
            f"📌 `.cps` (if setup is missing, say `/setup first`)"
        )

        await interaction.response.send_message(
            f"✅ **Your request has been created!** Check {ticket_channel.mention}.",
            ephemeral=True
        )

# ------------------------- Buy BGL Modal -------------------------

class BuyBGLModal(Modal):
    def __init__(self):
        super().__init__(title="💎 Buy BGL")

        self.add_item(TextInput(label="How many Ireng need?", required=True))
        self.add_item(TextInput(label="Via what payment method?", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        amount = self.children[0].value
        payment = self.children[1].value

        ticket_channel = await interaction.channel.create_thread(
            name=f"bgl-{interaction.user.name}",
            type=discord.ChannelType.public_thread
        )

        await ticket_channel.send(
            f"🔔 **New BGL Purchase Request!**\n"
            f"👤 **User:** {interaction.user.mention}\n"
            f"💰 **Amount:** `{amount}` Ireng\n"
            f"💳 **Payment:** `{payment}`\n\n"
            f"📌 `.gcash`"
        )

        await interaction.response.send_message(
            f"✅ **Your request has been created!** Check {ticket_channel.mention}.",
            ephemeral=True
        )

# ------------------------- Close Ticket Modal -------------------------

class CloseTicketModal(Modal):
    def __init__(self):
        super().__init__(title="🔒 Close Ticket")

        self.add_item(TextInput(label="Reason for closing?", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.children[0].value
        await interaction.channel.send(f"🔒 **Ticket closed!**\n📝 Reason: `{reason}`")
        await interaction.channel.delete()

# ------------------------- Ticket Interaction Handler -------------------------

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]

        if custom_id == "buy_script":
            await interaction.response.send_modal(BuyScriptModal())

        elif custom_id == "buy_bgl":
            await interaction.response.send_modal(BuyBGLModal())

        elif custom_id == "help_ticket":
            thread = await interaction.channel.create_thread(
                name=f"help-{interaction.user.name}",
                type=discord.ChannelType.public_thread
            )
            await thread.send(f"❓ **Help ticket opened by {interaction.user.mention}!**")
            await interaction.response.send_message(f"✅ Ticket created: {thread.mention}", ephemeral=True)

# ------------------------- Ticket Commands -------------------------

@bot.tree.command(name="setup_ticket", description="Set up the ticket panel (OWNER ONLY)")
async def setup_ticket(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=True)
        return

    await interaction.response.send_modal(TicketSetupModal())

@bot.command(name="post_ticket")
async def post_ticket(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    await ctx.send("Click below to open a ticket!", view=TicketView())

@bot.command(name="ticket")
async def ticket_command(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    await ctx.send("Click below to open a ticket!", view=TicketView())

# ------------------------- Close Ticket Command -------------------------

@bot.command(name="close")
async def close_ticket(ctx):
    if isinstance(ctx.channel, discord.Thread):  
        await ctx.send(f"🔒 {ctx.author.mention} is closing this ticket. Reason required.")
        await ctx.author.send_modal(CloseTicketModal())
    else:
        await ctx.send("❌ You can only use `.close` inside a ticket.")

# ------------------------- Run the Bot -------------------------

bot.run(TOKEN)
