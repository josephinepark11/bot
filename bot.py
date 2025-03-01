import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import os
import re, asyncio
from datetime import datetime
from dotenv import load_dotenv
from discord import ButtonStyle
from discord.ext.commands import has_permissions

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))  # Your Discord ID
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID")) # CATEGORY TICKET ID
TRANSCRIPT_CHANNEL_ID = int(os.getenv("TRANSCRIPT_CHANNEL_ID"))  # Change to your transcript channel ID



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


# ------------------------- Thread Close Button View -------------------------

class ThreadCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket_button")
    async def close_ticket_button(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(" This can only be used in a ticket thread.", ephemeral=True)
            return
        
        # Check if user has permission
        if interaction.channel.owner != interaction.user and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(" You don't have permission to close this ticket.", ephemeral=True)
            return
            
        # Open the close ticket modal
        await interaction.response.send_modal(CloseTicketModal(interaction.channel))

# ------------------------- Transcript View Button -------------------------


class TranscriptView(View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="📑 View Thread History", style=discord.ButtonStyle.blurple, custom_id="view_transcript_button")
    async def view_transcript(self, interaction: discord.Interaction, button: Button):
        # Here we'll retrieve and display the transcript
        await interaction.response.defer(ephemeral=True)
        
        # Get transcript from database or file system
        transcript_file = await get_transcript(self.ticket_id)
        
        if not transcript_file or not os.path.exists(transcript_file):
            await interaction.followup.send(" No transcript found for this ticket.", ephemeral=True)
            return
        
        # Send transcript as a file with ephemeral message
        await interaction.followup.send(
            f"📑 Transcript for ticket #{self.ticket_id}:", 
            file=discord.File(transcript_file), 
            ephemeral=True
        )

# ------------------------- Modified Close Ticket Modal -------------------------

class CloseTicketModal(Modal):
    def __init__(self, thread):
        super().__init__(title="🔒 Close Ticket")
        self.thread = thread
        self.add_item(TextInput(label="Reason for closing?", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.children[0].value
        
        try:
            transcript_channel = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
            if not transcript_channel:
                transcript_channel = interaction.channel.parent
                
            ticket_id = self.thread.id
            
            created_at = self.thread.created_at.strftime("%B %d, %Y %I:%M %p")
            closed_by = interaction.user.mention

            embed = discord.Embed(title="<a:triangle:1270931226236031026> Ticket Closed", color=discord.Color.red())
            embed.add_field(name="<a:nitroray:1341596662631501917> Ticket ID", value=f"`{ticket_id}`", inline=True)
            embed.add_field(name="<:bot:1241769461825011774> Opened By", value=f"{self.thread.owner.mention if self.thread.owner else 'Unknown'}", inline=True)
            embed.add_field(name="<:bot:1241769461825011774> Closed By", value=f"{closed_by}", inline=True)
            embed.add_field(name="<a:time_ray:1336527533935431822> Open Time", value=f"{created_at}", inline=True)
            embed.add_field(name="<:script:1270935350667378699>  Reason", value=f"`{reason}`", inline=False)
            embed.set_footer(text=f"Closed at {datetime.now().strftime('%B %d, %Y %I:%M %p')}")

            # Send with transcript view button
            view = TranscriptView(ticket_id)
            await transcript_channel.send(embed=embed, view=view)

            # Notify user before deletion
            await interaction.response.send_message("✅ Ticket has been closed and transcript saved.", ephemeral=True)
            
            # Add a delay before deleting the thread to ensure the response is seen
            await asyncio.sleep(3)
            
            # Archive and lock the thread instead of deleting it
            await self.thread.edit(archived=True, locked=True)
            
        except Exception as e:
            # Log the error and inform the user
            print(f"Error closing ticket: {e}")
            await interaction.response.send_message(f" Error closing ticket: {str(e)}", ephemeral=True)
# ------------------------- Helper Functions -------------------------

# Store thread messages in a database or file system
async def log_thread_messages(thread):
    """Log all messages in a thread for transcript purposes"""
    messages = []
    try:
        async for message in thread.history(limit=None, oldest_first=True):
            # Skip system messages and empty messages
            if not message.content and not message.embeds and not message.attachments:
                continue
                
            # Format message data
            msg_data = {
                "author": str(message.author),
                "author_id": str(message.author.id),
                "content": message.content,
                "timestamp": message.created_at.isoformat(),
                "attachments": [a.url for a in message.attachments],
                "embeds": [{"title": e.title, "description": e.description} for e in message.embeds if e.title or e.description]
            }
            messages.append(msg_data)
        
        # Save to file system
        transcript_file = await save_transcript(thread.id, messages)
        return transcript_file
        
    except Exception as e:
        print(f"Error logging thread messages: {e}")
        return None

async def save_transcript(ticket_id, messages):
    """Save transcript to file or database"""
    # Example implementation using files
    transcript_dir = "transcripts"
    os.makedirs(transcript_dir, exist_ok=True)
    
    # Save raw JSON for future reference
    json_filename = f"{transcript_dir}/{ticket_id}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=4)
    
    # Format into a text file for display
    formatted_file = f"{transcript_dir}/{ticket_id}_formatted.txt"
    with open(formatted_file, "w", encoding="utf-8") as f:
        f.write(f"TRANSCRIPT FOR TICKET #{ticket_id}\n")
        f.write("="*50 + "\n\n")
        
        for msg in messages:
            timestamp = datetime.fromisoformat(msg["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {msg['author']}:\n")
            
            if msg["content"]:
                f.write(f"{msg['content']}\n")
            
            # Include embed contents
            if msg["embeds"]:
                f.write("Embeds:\n")
                for embed in msg["embeds"]:
                    if embed.get("title"):
                        f.write(f"Title: {embed['title']}\n")
                    if embed.get("description"):
                        f.write(f"Description: {embed['description']}\n")
            
            if msg["attachments"]:
                f.write("Attachments:\n")
                for url in msg["attachments"]:
                    f.write(f"- {url}\n")
            
            f.write("\n" + "-"*50 + "\n\n")
    
    return formatted_file

async def get_transcript(ticket_id):
    """Retrieve transcript from storage and format for display"""
    transcript_file = f"transcripts/{ticket_id}_formatted.txt"
    
    if not os.path.exists(transcript_file):
        # Try to generate it from the JSON if it exists
        json_file = f"transcripts/{ticket_id}.json"
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    messages = json.load(f)
                    await save_transcript(ticket_id, messages)
                    if os.path.exists(transcript_file):
                        return transcript_file
                except:
                    return None
        return None
    
    return transcript_file

# Add this event handler to your bot
@bot.event
async def on_thread_member_remove(thread_member):
    """Event triggered when a member leaves a thread"""
    thread = thread_member.thread
    
    # Check if this is a ticket thread (you might want to improve this check)
    if isinstance(thread, discord.Thread) and thread.name.startswith("🎟"):
        # Check if the owner left and thread is not archived
        if thread_member.id == thread.owner_id and not thread.archived:
            # Wait a bit to see if they come back
            await asyncio.sleep(60)  # 1 minute grace period
            
            # Re-fetch thread to get current state
            updated_thread = bot.get_channel(thread.id)
            if not updated_thread or updated_thread.archived:
                return
                
            # Check if owner is still gone
            owner_present = False
            async for member in updated_thread.fetch_members():
                if member.id == thread.owner_id:
                    owner_present = True
                    break
            
            if not owner_present:
                # Auto-archive the thread
                embed = discord.Embed(
                    title="🔒 Thread Auto-Closed",
                    description="This ticket was automatically closed because the owner left the thread.",
                    color=discord.Color.orange()
                )
                
                try:
                    # Log messages before archiving
                    await log_thread_messages(updated_thread)
                    
                    # Send notification
                    await updated_thread.send(embed=embed)
                    
                    # Archive and lock the thread
                    await updated_thread.edit(archived=True, locked=True)
                    
                    # Notify in transcript channel
                    transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL_ID)
                    if transcript_channel:
                        ticket_id = updated_thread.id
                        close_embed = discord.Embed(
                            title="🔒 Ticket Auto-Closed", 
                            description=f"Ticket #{ticket_id} was automatically closed because the owner left the thread.",
                            color=discord.Color.orange()
                        )
                        view = TranscriptView(ticket_id)
                        await transcript_channel.send(embed=close_embed, view=view)
                        
                except Exception as e:
                    print(f"Error auto-closing thread: {e}")

# ------------------------- Modified Ticket Creation Functions -------------------------

# Update BuyScriptModal's on_submit method to add the close button
class BuyScriptModal(Modal):
    def __init__(self):
        super().__init__(title="🛒 Buy Script")
        self.add_item(TextInput(label="What script do you want to buy?", required=True))
        self.add_item(TextInput(label="What is your UID?", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        script_name = self.children[0].value
        user_uid = self.children[1].value

        # Create a private ticket thread
        thread = await interaction.channel.create_thread(
            name=f"🎟 script-{interaction.user.name}",
            type=discord.ChannelType.private_thread
        )

        # Get the CPS message from server settings
        guild_id = str(interaction.guild_id)
        cps_message = server_settings.get(guild_id, {}).get("cps", "`.cps` (if setup is missing, say `/setup` first)")
        
        embed = discord.Embed(title="<:script:1270935350667378699>  Buy Script Request!", color=discord.Color.random())
        embed.add_field(name="<:bot:1241769461825011774> User", value=interaction.user.mention, inline=True)
        embed.add_field(name="<:script:1270935350667378699> Script", value=f"`{script_name}`", inline=False)
        embed.add_field(name="<a:nitroray:1341596662631501917> UID", value=f"`{user_uid}`", inline=False)
        embed.add_field(name="📌", value=cps_message)
        embed.set_footer(text=f"Requested at {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
        
        # Add close button to the thread
        close_view = ThreadCloseView()
        await thread.send(interaction.user.mention, embed=embed, view=close_view)
        await interaction.response.send_message(f"✅ Ticket created: {thread.mention}", ephemeral=True)

# Update BuyBGLModal's on_submit method to add the close button
class BuyBGLModal(Modal):
    def __init__(self):
        super().__init__(title="🛒 Buy BGL")
        self.add_item(TextInput(label="How many Ireng do you need?", required=True))
        self.add_item(TextInput(label="Via what payment method?", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        amount = self.children[0].value
        payment_method = self.children[1].value

        # Create a private ticket thread
        thread = await interaction.channel.create_thread(
            name=f"🎟 bgl-{interaction.user.name}",
            type=discord.ChannelType.private_thread
        )

        # Get the GCASH message from server settings
        guild_id = str(interaction.guild_id)
        gcash_message = server_settings.get(guild_id, {}).get("gcash", "`.gcash`")

        embed = discord.Embed(title="<a:nitroray:1341596662631501917> Buy BGL Request!", color=discord.Color.orange())
        embed.add_field(name="<:bot:1241769461825011774> User", value=interaction.user.mention, inline=True)
        embed.add_field(name="<a:raybgl:1271323050800971878>  Amount", value=f"`{amount}`", inline=False)
        embed.add_field(name="<:dcray2:1341962996154368031> Payment Method", value=f"`{payment_method}`", inline=False)
        embed.add_field(name="📌", value=gcash_message)
        embed.set_footer(text=f"Requested at {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
        
        # Add close button to the thread
        close_view = ThreadCloseView()
        await thread.send(interaction.user.mention, embed=embed, view=close_view)
        await interaction.response.send_message(f"✅ Ticket created: {thread.mention}", ephemeral=True)

# ------------------------- Ticket Setup Modal -------------------------

# Fix for the TicketSetupModal
class TicketSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎟 Setup Ticket Panel")
        self.add_item(TextInput(label="Enter Ticket Description", required=True, style=discord.TextStyle.paragraph))
        self.add_item(TextInput(label="Optional GIF URL", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="TICKET SUPPORT",
            description=self.children[0].value,
            color=discord.Color.blue()
        )
        
        # Validate the URL before setting the image
        if self.children[1].value:
            url = self.children[1].value.strip()
            # Simple URL validation
            if url.startswith(('http://', 'https://')) and ('.' in url):
                embed.set_image(url=url)
            else:
                # Send a warning if URL is invalid
                await interaction.response.send_message(" Invalid image URL provided. Creating panel without image.", ephemeral=True)
                return
                
        # Set footer only if user has avatar
        if interaction.user.avatar:
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
        else:
            embed.set_footer(text=f"Requested by {interaction.user}")

        view = TicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel created!", ephemeral=True)

# ------------------------- Ticket View with Buttons -------------------------

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Buy Script", style=discord.ButtonStyle.red, custom_id="buy_script_button")
    async def buy_script(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(BuyScriptModal())

    @discord.ui.button(label="💎 Buy BGL", style=discord.ButtonStyle.blurple, custom_id="buy_bgl_button")
    async def buy_bgl(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(BuyBGLModal())

    @discord.ui.button(label="❓ Help", style=discord.ButtonStyle.gray, custom_id="help_ticket_button")
    async def help_ticket(self, interaction: discord.Interaction, button: Button):
        # Create a private thread for help
        thread = await interaction.channel.create_thread(
            name=f"🎟 help-{interaction.user.name}",
            type=discord.ChannelType.private_thread
        )

        # Add close button view
        close_view = ThreadCloseView()
        await thread.send(f"👤 **User:** {interaction.user.mention}\n❓ **Help request opened!**", view=close_view)
        await interaction.response.send_message(f"✅ Help ticket created: {thread.mention}", ephemeral=True)

# ------------------------- Original Commands (Preserved) -------------------------

# Setup Ticket Command
@bot.tree.command(name="setup_ticket", description="Set up the ticket panel (OWNER ONLY)")
async def setup_ticket(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message(" You are not authorized to use this command.", ephemeral=True)
        return

    await interaction.response.send_modal(TicketSetupModal())

# Close Ticket Command (preserved for backward compatibility)
@bot.command(name="close")
async def close_ticket(ctx):
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send(" You can only use `.close` inside a ticket thread.")
        return

    # Check if the user has permission
    if ctx.channel.owner != ctx.author and not ctx.author.guild_permissions.manage_channels:
        await ctx.send(" You don't have permission to close this ticket.")
        return

    # Send closing confirmation
    await ctx.send(f"📝 {ctx.author.mention} is closing this ticket.")
    
    # Open the close ticket modal
    await ctx.interaction.response.send_modal(CloseTicketModal(ctx.channel))

# Owner-Only Ticket Setup
@bot.command(name="post_ticket")
async def post_ticket(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send(" You are not authorized to use this command.")
        return

    await ctx.send("Click a button below to open a ticket!", view=TicketView())

@bot.command(name="ticket")
async def ticket_command(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send(" You are not authorized to use this command.")
        return

    await ctx.send("Click below to open a ticket!", view=TicketView())

# Create ticket function
async def create_ticket(interaction: discord.Interaction, title: str, description: str):
    """ Creates a private ticket channel inside the ticket category. """
    guild = interaction.guild
    category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),  # Hide from everyone
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)  # Bot access
    }

    ticket_channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name}",
        category=category,
        overwrites=overwrites
    )

    embed = discord.Embed(title=title, description=description, color=discord.Color.green())
    embed.set_footer(text=f"Ticket opened by {interaction.user}", icon_url=interaction.user.avatar.url)
    
    # Add close button to the channel
    close_view = ThreadCloseView()
    await ticket_channel.send(f"🎟 **Ticket Opened by {interaction.user.mention}!**", embed=embed, view=close_view)
    await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)



# ------------------------- Run the Bot -------------------------

bot.run(TOKEN)
