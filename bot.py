import os

import dotenv
import interactions
from datetime import datetime
from interactions import slash_command, SlashContext, slash_option, OptionType, Task, IntervalTrigger

dotenv.load_dotenv()
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')

bot = interactions.Client(intents=interactions.Intents.DEFAULT)


@interactions.listen()
async def on_startup():
    print("Bot is ready!")


# @interactions.listen(event_name=interactions.events.MessageCreate)
# async def on_message_create(event):
#     message_create_event = interactions.events.MessageCreate(event)
#     print(message_create_event.message)


@slash_command(name="joining", description="command when user is joining soon")
@slash_option(
    name="user",
    description="joining user's tag",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="when",
    description="ex) 0730 1520 2330",
    required=True,
    opt_type=OptionType.INTEGER
)
async def on_player_joining(ctx: SlashContext, user: interactions.User, when: int):
    when_str = str(when).zfill(4)
    joining_time = datetime.strptime(when_str, "%H%M").time()

    # TODO: save DB?

    await ctx.send(user.display_name + " is going to join at " + joining_time.isoformat())


@Task.create(IntervalTrigger(minutes=1)) # TODO: change to thread sleep/waking method
async def check_user_joined():

    print("TODO HERE")


bot.start(discord_bot_token)
