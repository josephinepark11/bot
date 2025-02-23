import discord
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput, Button
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Bot configuration
COMMAND_PREFIX = '.'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Server settings storage
SETTINGS_FILE = 'server_settings.json'
server_settings = {}

# Load settings from JSON file
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}  # Return empty if file is corrupted
    return {}

# Save settings to JSON file
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
    server_settings.update(load_settings())  # Merge loaded settings
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Modal for entering setup messages
class SetupModal(Modal):
    def __init__(self, setting_name: str):
        super().__init__(title=f"Setup {setting_name.upper()}")
        self.setting_name = setting_name
        self.add_item(TextInput(
            label="Enter the message:",
            style=discord.TextStyle.paragraph  # Larger text box
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # Fixes the error

        guild_id = str(interaction.guild_id)
        if guild_id not in server_settings:
            server_settings[guild_id] = {}

        server_settings[guild_id][self.setting_name] = self.children[0].value
        save_settings()

        # ✅ Confirmation message now includes the correct command
        await interaction.followup.send(
            f" {self.setting_name.upper()} has been set up! Do `.{self.setting_name}` to show the message.",
            ephemeral=True
        )

# Dropdown menu for setup
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

@bot.tree.command(name="setup", description="Set up messages for commands")
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message("Select an option to set up:", view=SetupView(), ephemeral=True)

# Function to display stored messages
async def display_command(ctx, command_name: str):
    guild_id = str(ctx.guild.id)
    message = server_settings.get(guild_id, {}).get(command_name)
    if message:
        await ctx.send(message)
    else:
        await ctx.send(f"No {command_name.upper()} message has been set. Use `/setup` to set it up.")

# Commands to display messages
commands_list = {
    "rgt": "rgt", "uid": "uid", "gcash": "gcash", 
    "rategt": "rgtrate", "rgcash": "rgcash", "rbin": "binancerate"
}

for cmd, setting in commands_list.items():
    async def command_func(ctx, command_name=setting):
        await display_command(ctx, command_name)
    command_func.__name__ = f"display_{cmd}"  # Unique function name to avoid errors
    bot.command(name=cmd)(command_func)

# ------------------------- /raypost Command -------------------------

class PostModal(Modal):
    def __init__(self):
        super().__init__(title="Create a Post")

        # Large description box
        self.description = TextInput(
            label="Description:",
            style=discord.TextStyle.paragraph,
            placeholder="Enter the content here (max 4000 characters)",
            max_length=4000
        )
        self.add_item(self.description)

        # Optional GIF URL
        self.gif_url = TextInput(
            label="GIF URL (Optional):",
            style=discord.TextStyle.short,
            placeholder="Enter a GIF URL (optional)",
            required=False
        )
        self.add_item(self.gif_url)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(description=self.description.value, color=discord.Color.blue())
        
        if self.gif_url.value:
            embed.set_image(url=self.gif_url.value)

        view = PostView(embed)
        await interaction.response.send_message("Review your post and confirm:", embed=embed, view=view, ephemeral=True)

class PostView(View):
    def __init__(self, embed):
        super().__init__(timeout=60)
        self.embed = embed

        # Post button
        self.post_button = Button(label="Post", style=discord.ButtonStyle.green)
        self.post_button.callback = self.post_message
        self.add_item(self.post_button)

        # Cancel button
        self.cancel_button = Button(label="Cancel", style=discord.ButtonStyle.red)
        self.cancel_button.callback = self.cancel_message
        self.add_item(self.cancel_button)

    async def post_message(self, interaction: discord.Interaction):
        await interaction.channel.send(embed=self.embed)
        await interaction.response.send_message(" Your post has been published!", ephemeral=True)
        self.stop()

    async def cancel_message(self, interaction: discord.Interaction):
        await interaction.response.send_message(" Post creation was canceled.", ephemeral=True)
        self.stop()

@bot.tree.command(name="raypost", description="Create a custom post with a GUI")
async def raypost(interaction: discord.Interaction):
    await interaction.response.send_modal(PostModal())

# ------------------------- Bot Runner -------------------------

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN is missing in .env file!")
