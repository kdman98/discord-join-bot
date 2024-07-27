import logging
import os

import dotenv
import interactions
from datetime import datetime, timedelta

import mysql.connector
from mysql.connector import Error
from interactions import slash_command, SlashContext, slash_option, OptionType, Task, IntervalTrigger, listen

dotenv.load_dotenv()
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')
mysql_user = os.getenv('MYSQL_DATABASE_USER')
mysql_password = os.getenv('MYSQL_DATABASE_PASSWORD')


async def fetch_all_guilds_of_bot(target_bot):
    logging.log(level=logging.INFO, msg="Fetching all guilds")
    for guild in target_bot.guilds:
        await target_bot.fetch_guild(guild.id)


bot = interactions.Client(intents=interactions.Intents.ALL, fetch_members=True)
fetch_all_guilds_of_bot(bot)

logging.basicConfig(
    format='%(asctime)s %(levelname)s:%(message)s',
    level=logging.INFO,
    datefmt='%m/%d/%Y %I:%M:%S %p',
)
logger = logging.getLogger("bot_logger")
stream_handler = logging.StreamHandler()

formatter_log = logging.Formatter("%(asctime)s %(levelname)s:%(message)s")
handler_log = logging.FileHandler("bot.log")
handler_log.setLevel(logging.INFO)
handler_log.setFormatter(formatter_log)

logger.addHandler(stream_handler)
logger.addHandler(handler_log)


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
            logging.log(level=logging.INFO, msg="Connected to MySQL database")
        return connection
    except Error as e:
        logging.log(level=logging.CRITICAL, msg=f"Error: '{e}'")
        return None


connection = create_connection()


@listen(event_name=interactions.api.events.Startup)
async def on_startup():
    check_user_joined_with_interval.start()
    logging.log(level=logging.INFO, msg="Bot is ready!")


@slash_command(name="help", description="I NEED HELLLLLP")
async def help_command(ctx: SlashContext):
    help_message = (
        "OY, I'm describing a simple using method for our PITY {}. Listen carefully.\n"
        "- /join [@player] [joining time - four digit] to decide when to join. When you're not then, bot alerts you. "
        "haha!\n"
        "- /list to check who is joining when.\n"
        "- /clear removes ALL LISTS take care.\n"
        "this is an alpha version, so tell kdman98@naver.com if any problem occurred."
    ).format(ctx.user.mention)
    await ctx.send(help_message)


@slash_command(name="join", description="command when user is joining soon")
@slash_option(
    name="user",
    description="joining user's tag",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="when",
    description="ex) 07:30 -> 0730, 14:00 -> 1400",
    required=True,
    opt_type=OptionType.INTEGER
)
async def on_player_joining(ctx: SlashContext, user: interactions.User, when: int):
    if not (0 <= when < 2400):
        await ctx.send(
            user.mention + ", time range is out of bounds! (00:00 ~ 23:59)"
        )
        return
    when_str = str(when).zfill(4)
    joining_time = datetime.strptime(when_str, "%H%M").time()

    joining_time = datetime.now().replace(hour=joining_time.hour, minute=joining_time.minute, second=0)
    registered_time = datetime.now()
    if joining_time.time() < datetime.now().time():
        joining_time += timedelta(days=1)

    if len(search_single_user_joining_waitlist_sql(ctx.guild.id, user.id)) == 0:
        add_user_joining_waitlist_sql(ctx.guild.id, user.id, joining_time, registered_time)
    else:
        update_user_joining_waitlist_sql(ctx.guild.id, user.id, joining_time)

    await ctx.send(
        user.mention + " joins at " + "**" + str(joining_time.hour).zfill(2) + ":"
        + str(joining_time.minute).zfill(2) + "**"
    )


@slash_command(name="clear", description="clear joining waitlist")
async def clear_joining_waitlist(ctx: SlashContext):
    delete_all_guild_joining_waitlist_sql(ctx.guild.id)
    await ctx.send(
        ctx.user.mention + " cleared joining waitlist successfully"
    )


@slash_command(name="list", description="list up users when they are joining")
async def list_up_joins(ctx: SlashContext):
    waitlist = search_user_joining_waitlist_by_guild_id_sql(ctx.guild.id)
    waitlist = sorted(waitlist, key=lambda x: x[3])

    if len(waitlist) == 0:
        await ctx.send("Users not joined yet :(")
        return

    now = datetime.now()
    user_dict_by_id = {}
    for wait_each in waitlist:
        if wait_each[2] not in user_dict_by_id:
            # await bot.fetch_member(wait_each[2], wait_each[1]) # ignored by option for fetching all members at start
            # might be a fix for taking too long at startup, but will await work well here?
            user_dict_by_id[wait_each[2]] = bot.get_member(wait_each[2], wait_each[1])

    sending_message = ""
    sending_message += "user / joining time / voice online / late?\n"

    for idx, row in enumerate(waitlist):
        user_info = user_dict_by_id[row[2]]
        sending_message += "{}. {} / **{}** / {} / {}".format(
            idx + 1,
            user_info.display_name,
            row[3].strftime("%H:%M"),
            ":white_check_mark:" if user_info.voice else ":x:",
            ":ok:" if user_info.voice or now < row[3] else ":alarm_clock:"
        )
        sending_message += "\n"

    await ctx.send(
        sending_message
    )


@Task.create(IntervalTrigger(minutes=15))  # TODO: change to thread sleep/waking method and less search, with toggle
async def check_user_joined_with_interval():
    now = datetime.now()
    time_passed_users_row = search_user_joining_waitlist_joining_time_passed_sql(
        now
    )  # TODO: guild, user, time - make it Entity

    user_dict_by_id = {}
    for row in time_passed_users_row:
        if row[1] not in user_dict_by_id:
            user_dict_by_id[row[1]] = bot.get_member(row[1], row[0])

    grouped_users_info_by_guild = {}
    for row in time_passed_users_row:
        guild_uid = row[0]
        if guild_uid not in grouped_users_info_by_guild:
            grouped_users_info_by_guild[guild_uid] = []
        grouped_users_info_by_guild[guild_uid].append(row)

    for guild_uid, users_row in grouped_users_info_by_guild.items():
        guild = bot.get_guild(guild_uid)
        message = "## --- Players not joined yet (Alerts done only once) ---\n"
        message += "User / Planned Time\n"
        for user in users_row:
            user_info = bot.get_member(user[1], user[0])
            if not user_info.voice or user_info.voice.channel.guild.id != guild_uid:
                message += "{} / **{}**\n".format(
                    user_info.mention,
                    user[2].strftime("%H:%M"),
                )
                delete_user_joining_waitlist_sql(guild_uid, user_info.id) # TODO: instead delete, add checking column

        await guild.system_channel.send(message)


# @slash_command(name="toggle_join_alert", description="toggle to alert user if joined in time")
# @check(is_owner())
async def toggle_join_alert(ctx: SlashContext):
    # TODO: WIP
    Task.start(check_user_joined_with_interval(ctx.guild.id))  # WHAT?
    await ctx.send(
        ctx.user.mention + " toggled joining alert successfully"
    )


def add_user_joining_waitlist_sql(guild_uid, user_uid, joining_time, registered_time):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"INSERT INTO join_waitlist (guild_uid, user_uid, joining_time, registered_time) VALUES ('{guild_uid}', '{user_uid}', '{joining_time}', '{registered_time}')")
    connection.commit()
    cursor.close()


def delete_all_guild_joining_waitlist_sql(guild_uid):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"DELETE FROM join_waitlist WHERE guild_uid = '{guild_uid}'"
    )
    connection.commit()
    cursor.close()


def search_user_joining_waitlist_joining_time_passed_sql(now):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"SELECT guild_uid, user_uid, joining_time FROM join_waitlist WHERE joining_time <= '{now}'"
    )
    member_waitlist = cursor.fetchall()
    cursor.close()

    return member_waitlist


def search_user_joining_waitlist_by_guild_id_sql(guild_id):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"SELECT * FROM join_waitlist WHERE guild_uid < '{guild_id}'"
    )
    member_waitlist = cursor.fetchall()
    cursor.close()

    return member_waitlist


def search_single_user_joining_waitlist_sql(guild_uid, user_uid):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"SELECT * FROM join_waitlist WHERE guild_uid = '{guild_uid}' AND user_uid = '{user_uid}'"
    )
    member_waitlist = cursor.fetchall()
    cursor.close()
    return member_waitlist


def update_user_joining_waitlist_sql(guild_uid, user_uid, joining_time):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"UPDATE join_waitlist SET joining_time = '{joining_time}' WHERE guild_uid = '{guild_uid}' AND user_uid = '{user_uid}'"
    )
    connection.commit()
    cursor.close()


def delete_user_joining_waitlist_sql(guild_uid, user_uid):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"DELETE FROM join_waitlist WHERE guild_uid = '{guild_uid}' AND user_uid = '{user_uid}'"
    )
    connection.commit()
    cursor.close()


bot.start(discord_bot_token)
