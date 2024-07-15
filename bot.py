import os

import dotenv
import interactions
from datetime import datetime, timedelta

import mysql.connector
from mysql.connector import Error
from interactions import slash_command, SlashContext, slash_option, OptionType, Task, IntervalTrigger

dotenv.load_dotenv()
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')
mysql_user = os.getenv('MYSQL_DATABASE_USER')
mysql_password = os.getenv('MYSQL_DATABASE_PASSWORD')

bot = interactions.Client(intents=interactions.Intents.DEFAULT)


# MySQL
def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='im_joining_soon_bot',
            user=mysql_user,
            password=mysql_password,
        )
        if connection.is_connected():
            print('Connected to MySQL database')
        return connection
    except Error as e:
        print(f"Error: '{e}'")
        return None


connection = create_connection()


@interactions.listen()
async def on_startup():
    print("Bot is ready!")


@slash_command(name="joining", description="command when user is joining soon")
@slash_option(
    name="user",
    description="joining user's tag",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="when",
    description="ex) 0730 1520 2330 115",
    required=True,
    opt_type=OptionType.INTEGER
)
async def on_player_joining(ctx: SlashContext, user: interactions.User, when: int):
    when_str = str(when).zfill(4)
    joining_time = datetime.strptime(when_str, "%H%M").time()

    # TODO: save DB?
    add_user_joining_waitlist_sql(ctx.guild.id, user.id, joining_time)

    await ctx.send(
        user.mention + " is going to join at " + str(joining_time.hour).zfill(2) + ":"
        + str(joining_time.minute).zfill(2)
    )


@slash_command(name="clear", description="clear joining waitlist")
async def clear_joining_waitlist(ctx: SlashContext):
    clear_joining_waitlist_sql(ctx.guild.id)
    await ctx.send(
        ctx.user.mention + " cleared joining waitlist successfully"
    )


@slash_command(name="toggle_join_alert", description="toggle to alert user if joined in time")
async def toggle_join_alert(ctx: SlashContext):
    # TODO: only admin must use this
    Task.start(check_user_joined(ctx.guild.id)) # WHAT?
    await ctx.send(
        ctx.user.mention + " toggled joining alert successfully"
    )


@Task.create(IntervalTrigger(minutes=5))  # TODO: change to thread sleep/waking method and less search
async def check_user_joined(guild_uid):
    search_user_joining_waitlist_sql(guild_uid)
    print("check user")


def add_user_joining_waitlist_sql(guild_uid, user_uid, joining_time):
    joining_time = datetime.now().replace(hour=joining_time.hour, minute=joining_time.minute)
    registered_time = datetime.now()
    if joining_time.time() < datetime.now().time():
        joining_time += timedelta(days=1)

    cursor = connection.cursor()
    cursor.execute(
        f"INSERT INTO join_waitlist (guild_uid, user_uid, joining_time, registered_time) VALUES ('{guild_uid}', '{user_uid}', '{joining_time}', '{registered_time}')")
    connection.commit()


def clear_joining_waitlist_sql(guild_uid):
    cursor = connection.cursor()
    cursor.execute(
        f"DELETE FROM join_waitlist WHERE guild_uid = '{guild_uid}'"
    )
    connection.commit()


def search_user_joining_waitlist_sql(guild_uid):
    cursor = connection.cursor()
    member_waitlist = cursor.execute(
        f"SELECT * FROM join_waitlist WHERE guild_uid = '{guild_uid}'"
    )
    return member_waitlist


bot.start(discord_bot_token)
