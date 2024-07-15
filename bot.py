import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import dotenv

intents = discord.Intents.default()
intents.members = True

dotenv.load_dotenv()
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')
bot = commands.Bot(command_prefix='!', intents=intents)

user_alerts = {}

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    check_users.start()

@bot.command()
async def join(ctx, time: str):
    user = ctx.author
    try:
        alert_time = datetime.strptime(time, "%H:%M").time()
        user_alerts[user.id] = alert_time
        await ctx.send(f'{user.mention}, you will be alerted if you are offline at {time}.')
    except ValueError:
        await ctx.send('Invalid time format. Please use HH:MM.')

@tasks.loop(minutes=1)
async def check_users():
    current_time = datetime.utcnow().time()
    for user_id, alert_time in user_alerts.items():
        if current_time.hour == alert_time.hour and current_time.minute == alert_time.minute:
            user = bot.get_user(user_id)
            if user:
                member = await bot.get_guild(1).fetch_member(user_id) # get guild..?
                if member and not member.status == discord.Status.online:
                    try:
                        await user.send(f'You are offline at your scheduled time: {alert_time}')
                    except discord.Forbidden:
                        pass

bot.run(discord_bot_token)
