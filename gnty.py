import discord
from discord.ext import commands
from pymongo import MongoClient
import re
from collections import Counter
import requests
from dotenv import load_dotenv
import os
import webserver
# MongoDB setup
MONGO_URI = "mongodb+srv://khalifakalansari:Kh2382009@cluster0.qm03hvg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace this with your actual MongoDB URI
client = MongoClient(MONGO_URI)
db = client["discord_gnty"]
logs_collection = db["logs"]
clips_collection = db['clips']   # Collection for storing clips

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=",", intents=intents, help_command=None)

# Allowed server
ALLOWED_SERVER_ID = 1330196005966053498
BOT_OWNER_ID = 993245909079052369

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Streaming(name="Ghnaty Support", url="https://discord.gg/gnty"))
    print(f"Logged in as {bot.user}")

@bot.command()
async def add(ctx, action: str, user: str, *, reason: str):
    """Adds a ban or warning to the log."""
    if ctx.guild.id != ALLOWED_SERVER_ID:
        return
    
    action = action.lower()
    await ctx.message.delete()
    
    # Store the moderator's username (not the mention)
    moderator = ctx.author.name  # Use the username instead of mention
    
    if action == "warn":
        existing_warnings = logs_collection.count_documents({"user": user, "action": "warn"})
        warning_count = existing_warnings + 1
        logs_collection.insert_one({
            "user": user,
            "action": "warn",
            "count": warning_count,
            "reason": reason,
            "moderator": moderator,  # Store the username of the moderator
        })
        
        embed = discord.Embed(title="User log warned", color=discord.Color.greyple())
        embed.add_field(name="User", value=user, inline=True)
        embed.add_field(name="Action", value="Warn", inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Moderation", value=moderator, inline=True)  # Display the username here
        embed.add_field(name="Warning Counter", value=str(warning_count), inline=True)
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
    
    elif action == "ban":
        duration_str = re.search(r"(\d+[ymdhs])", reason)
        if not duration_str:
            return await ctx.send("Please specify a valid duration for the ban, e.g., '1d'.")
        duration_str = duration_str.group(1)
        
        existing_bans = logs_collection.count_documents({"user": user, "action": "ban"})
        ban_number = existing_bans + 1
        logs_collection.insert_one({
            "user": user,
            "action": "ban",
            "duration": duration_str,
            "reason": reason,
            "ban_number": ban_number,
            "moderator": moderator,  # Store the username of the moderator
        })
        
        embed = discord.Embed(title="User Ban logged", color=discord.Color.greyple())
        embed.add_field(name="User", value=user, inline=True)
        embed.add_field(name="Action", value="Ban", inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Time", value=duration_str, inline=True)
        embed.add_field(name="Moderation", value=moderator, inline=True)  # Display the username here
        embed.add_field(name="Ban Counter", value=str(ban_number), inline=True)
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")


@bot.command()
async def search(ctx, *, user: str):
    """Shows a user's warning and ban history."""
    if ctx.guild.id != ALLOWED_SERVER_ID:
        return
    
    warnings = logs_collection.count_documents({"user": user, "action": "warn"})
    bans = logs_collection.count_documents({"user": user, "action": "ban"})
    
    embed = discord.Embed(title=f"{user}'s History", color=discord.Color.greyple())
    embed.add_field(name="Warnings", value=str(warnings), inline=True)
    embed.add_field(name="Bans", value=str(bans), inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def clear_all(ctx):
    """Clears all warnings and bans for every user, only for the bot owner."""
    if ctx.author.id != BOT_OWNER_ID:
        return await ctx.send("You do not have permission to run this command.")
    
    logs_collection.delete_many({"action": {"$in": ["warn", "ban"]}})
    await ctx.send("All warnings and bans have been cleared.")

@bot.command()
async def remove_warn(ctx, user: str, warn_number: int):
    """Removes a specific warning for a user based on their username and the warning number."""
    if ctx.guild.id != ALLOWED_SERVER_ID:
        return
    
    # Find all warnings for the user
    warnings = logs_collection.find({"user": user, "action": "warn"}).sort("timestamp", 1)  # Sorting by timestamp
    
    # Get the warning with the given number
    warn_to_remove = None
    for count, warning in enumerate(warnings, start=1):
        if count == warn_number:
            warn_to_remove = warning
            break

    if warn_to_remove:
        # Remove the warning from the database
        logs_collection.delete_one({"_id": warn_to_remove["_id"]})
        await ctx.send(f"Warning {warn_number} for {user} has been removed.")
    else:
        await ctx.send(f"No warning with number {warn_number} found for {user}.")

@bot.command()
async def remove_ban(ctx, user: str, ban_number: int):
    """Removes a specific ban for a user based on their username and the ban number."""
    if ctx.guild.id != ALLOWED_SERVER_ID:
        return
    
    # Find all bans for the user
    bans = logs_collection.find({"user": user, "action": "ban"}).sort("timestamp", 1)  # Sorting by timestamp
    
    # Get the ban with the given number
    ban_to_remove = None
    for count, ban in enumerate(bans, start=1):
        if count == ban_number:
            ban_to_remove = ban
            break

    if ban_to_remove:
        # Remove the ban from the database
        logs_collection.delete_one({"_id": ban_to_remove["_id"]})
        await ctx.send(f"Ban {ban_number} for {user} has been removed.")
    else:
        await ctx.send(f"No ban with number {ban_number} found for {user}.")



@bot.command()
async def top(ctx, page: int = 1):
    """Shows the top moderators based on the period (alltime)."""
    if ctx.guild.id != ALLOWED_SERVER_ID:
        return

    # Query logs for all-time period
    logs = list(logs_collection.find({}))
    moderators = [log["moderator"] for log in logs if "moderator" in log]

    # Count warnings and bans for each moderator
    warning_count = Counter()
    ban_count = Counter()

    for log in logs:
        if "moderator" in log:
            if log["action"] == "warn":
                warning_count[log["moderator"]] += 1
            elif log["action"] == "ban":
                ban_count[log["moderator"]] += 1

    # Combine the warning and ban counts for each moderator
    top_moderators = []
    for moderator in warning_count.keys() | ban_count.keys():
        top_moderators.append((moderator, warning_count[moderator], ban_count[moderator]))

    # Sort the top moderators based on the total actions (sum of warnings and bans)
    top_moderators.sort(key=lambda x: (x[1] + x[2]), reverse=True)

    # Pagination logic: get the slice of 5 items for the current page
    items_per_page = 5
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_moderators = top_moderators[start_index:end_index]

    # Format the embed
    embed = discord.Embed(title=f"Top Moderators - Page {page}", color=discord.Color.greyple())

    # Emojis for 1st, 2nd, and 3rd places
    place_emojis = ["🥇", "🥈", "🥉"]

    # Add the top 1, 2, 3 and then numbered moderators
    for i, (moderator, warn_count, ban_count) in enumerate(page_moderators, start=start_index + 1):
        user_mention = moderator  # Use the mention directly
        if i <= 3:
            place_emoji = place_emojis[i - 1]  # Assign place emoji for top 3
        else:
            place_emoji = f"{i}"  # Use number for others

        # Add the field with all info on the same line
        embed.add_field(name=f"{place_emoji} {user_mention}", value=f"{warn_count} warnings | {ban_count} bans", inline=False)

    # Add footer with page info and total pages
    total_pages = (len(top_moderators) // items_per_page) + (1 if len(top_moderators) % items_per_page > 0 else 0)
    embed.set_footer(text=f"Page {page}/{total_pages}")

    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    """Displays the help message with available commands."""
    if ctx.guild.id != ALLOWED_SERVER_ID:
        return
    
    embed = discord.Embed(title="Help", description="Available Commands:", color=discord.Color.greyple())
    embed.add_field(name=",add [warn/ban] [user] [reason]", value="Adds a warning or ban to a user.", inline=False)
    embed.add_field(name=",search [user]", value="Shows a user's warning and ban history.", inline=False)
    embed.add_field(name=",clear_all", value="Clears all warnings and bans (Bot owner only).", inline=False)
    embed.add_field(name=",remove_warn [user] [warn_number]", value="Removes a specific warning for a user.", inline=False)
    embed.add_field(name=",remove_ban [user] [ban_number]", value="Removes a specific ban for a user.", inline=False)
    embed.add_field(name=",top [page]", value="Shows the top moderators based on the period (alltime).", inline=False)
    embed.add_field(name=",clip [clip_url] [description]", value="Adds a clip to the database.", inline=False)
    embed.add_field(name=",clips", value="Shows all clips stored in the database.", inline=False)
    await ctx.send(embed=embed)

from datetime import datetime
import os

@bot.command()
async def clip(ctx, user: str):
    """Reposts the attachment from the user's message, mentions the user, and deletes the original message."""
    if ctx.message.attachments:
        # Get the attachment from the message
        attachment = ctx.message.attachments[0]
        
        # Check if the file size is too large (Discord max file size is 8MB)
        if attachment.size > 8 * 1024 * 1024:
            await ctx.send("This content is too big. Try to compress it using this tool: https://www.freeconvert.com/video-compressor")
            return

        # Download the file to repost it
        file = await attachment.to_file()

        # Save clip to MongoDB
        clip_data = {
            "user": user,
            "clip": attachment.url,
            "timestamp": datetime.now().isoformat()  # Current time without timezone
        }
        clips_collection.insert_one(clip_data)

        # Create a message mentioning the user and sending the attachment
        new_message = await ctx.send(f"Clip of {user}: ", file=file)
        
        # Delete the original message
        await ctx.message.delete()

        # Optionally, you can add a reaction or log the action if needed
        await new_message.add_reaction("✅")
        
    else:
        await ctx.send("No attachment found in the message to clip.")

@bot.command()
async def send_message(ctx, *, message: str):
    """Sends a message with a length check."""
    # Check if the message length exceeds Discord's 2000 character limit
    if len(message) > 2000:
        await ctx.send("This content is too big. Try to compress it using this tool: https://www.freeconvert.com/video-compressor")
    else:
        await ctx.send(message)

@bot.command()
async def clips(ctx, user: str):
    """Fetches the proof image URL or clip URLs of a user from the database and sends them in the channel."""
    
    # Query the MongoDB database for the user's clips
    user_clips = clips_collection.find({
        "$or": [{"user": user}, {"users": user}]
    })

    # Convert the cursor to a list and check if it's empty
    user_clips_list = list(user_clips)

    if user_clips_list:  # If there are clips found for the user
        proof_or_clip_urls = []
        
        # Iterate through the clips and get the available field (proof_image_url or clip)
        for clip in user_clips_list:
            proof_url = clip.get("proof_image_url")
            clip_url = clip.get("clip")

            if proof_url:
                proof_or_clip_urls.append(proof_url)
            elif clip_url:
                proof_or_clip_urls.append(clip_url)
        
        if proof_or_clip_urls:
            # Send the proof or clip URLs in a numbered list format
            proof_message = "\n".join([f"{i+1}. {url}" for i, url in enumerate(proof_or_clip_urls)])
            await ctx.send(f"Proof or clips for user {user}:\n{proof_message}")
        else:
            await ctx.send(f"No proof or clips found for user {user}.")
    else:
        await ctx.send(f"No clips found for user {user}.")


webserver.keep_alive()
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
