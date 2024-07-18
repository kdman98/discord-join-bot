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


@listen(event_name=interactions.events.Startup)
async def on_startup():
    print("Bot is ready!")


@slash_command(name="help", description="I NEED HELLLLLP")
async def help_command(ctx: SlashContext):
    help_message = (
        "좋아, 우리 불쌍한 {}이를 위해 설명할테니까 잘 들어.\n"
        "- /join (참여자) (참여시간 - 4자리 숫자) 로 언제 참여할지 설정해.\n"
        "- /list 로 언제 누가 참여할지 확인해.\n"
        "- /clear 를 하면 모든 리스트가 날아가. 급할때만 쓰라고.\n"
        "초기 버전이라 기능이 완벽하지 않을 수 있으니까 뭔가 문제가 생기면 만든 사람한테 뭐라 하라고. 띨띨아."
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
        print("add", user.display_name)
        add_user_joining_waitlist_sql(ctx.guild.id, user.id, joining_time, registered_time)
    else:
        print("update", user.display_name)
        update_user_joining_waitlist_sql(ctx.guild.id, user.id, joining_time)

    await ctx.send(
        user.mention + " is going to join at " + str(joining_time.hour).zfill(2) + ":"
        + str(joining_time.minute).zfill(2)
    )


@slash_command(name="clear", description="clear joining waitlist")
async def clear_joining_waitlist(ctx: SlashContext):
    delete_all_guild_joining_waitlist_sql(ctx.guild.id)
    await ctx.send(
        ctx.user.mention + " cleared joining waitlist successfully"
    )


@slash_command(name="list", description="list up users when they are joining")
async def list_up_joins(ctx: SlashContext):
    waitlist = search_user_joining_waitlist_sql(ctx.guild.id)

    if waitlist is None:
        await ctx.send("Users not joined yet :(")
        return

    now = datetime.now()
    user_dict_by_id = {}
    for wait_each in waitlist:
        if wait_each[3] not in user_dict_by_id:
            user_dict_by_id[wait_each[2]] = bot.get_member(wait_each[2], wait_each[1])

    sending_message = "### Online users' join list will be deleted soon after.\n\n"
    sending_message += "Nickname / Joining time / Voice Channel\n"  # TODO: to table
    sending_message += "---------------------------------------\n"  # TODO: to table

    for idx, row in enumerate(waitlist):
        user_info = user_dict_by_id[row[2]]
        sending_message += "{}. {} / {} / {}".format(
            idx + 1, user_info.display_name, row[3].strftime("%H:%M"), "Online" if user_info.voice else "Offline"
        )
        sending_message += "\n"
        if user_info.voice:
            delete_user_joining_waitlist_sql(ctx.guild.id, user_info.id)

    await ctx.send(
        sending_message
    )


# @slash_command(name="toggle_join_alert", description="toggle to alert user if joined in time")
# @check(is_owner())
async def toggle_join_alert(ctx: SlashContext):
    # TODO: WIP
    Task.start(check_user_joined_with_interval(ctx.guild.id))  # WHAT?
    await ctx.send(
        ctx.user.mention + " toggled joining alert successfully"
    )


@Task.create(IntervalTrigger(minutes=5))  # TODO: change to thread sleep/waking method and less search
async def check_user_joined_with_interval(guild_uid):
    search_user_joining_waitlist_sql(guild_uid)
    print("check user")


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


def search_user_joining_waitlist_sql(guild_uid):
    cursor = connection.cursor(buffered=True)
    cursor.execute(
        f"SELECT * FROM join_waitlist WHERE guild_uid = '{guild_uid}'"
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
