import logging
from datetime import datetime
from typing import Union

import arrow
import pytz
from dateutil import parser as dateparser
import discord
from discord_slash import SlashCommand, SlashContext, SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option

from botto import responses
from botto.models import AirTableError, Timezone
from botto.reminder_manager import (
    ReminderManager,
    TimeTravelError,
    ReminderParsingError,
)
from botto.storage import TimezoneStorage
from botto.storage.timezone_storage import TlderNotFoundError

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def person_option(desc: str, autocomplete: bool):
    return create_option(
        name="person",
        description=desc,
        option_type=SlashCommandOptionType.USER
        if autocomplete
        else SlashCommandOptionType.STRING,
        required=True,
    )


message_option = create_option(
    name="message",
    description="The message to send.",
    option_type=SlashCommandOptionType.STRING,
    required=False,
)


def setup_slash(
    client: discord.Client,
    config: dict,
    reminder_manager: ReminderManager,
    timezones: TimezoneStorage,
):
    slash = SlashCommand(client, sync_commands=True, delete_from_unused_guilds=True)

    @slash.slash(
        name="ping",
        description="Checks Tildy's response time to Discord",
        # guild_ids=[833842753799848016],
    )
    async def ping(
        ctx: SlashContext,
    ):
        log.debug(f"/ping from {ctx.author}")
        await ctx.send(f"Pong! ({ctx.bot.latency * 1000}ms)")

    async def _yell(ctx: SlashContext, person: Union[str, discord.Member], **kwargs):
        message = kwargs.get("message")
        log.debug(f"/yell from {ctx.author.id} at {person}: '{message}'")
        message_length = len(message)
        if message_length > 280:
            log.info(f"Message was {message_length} rejecting")
            await ctx.send("Please limit your yelling to the length of a tweet 🙄")
            return
        response_text = responses.yell_at_someone(person, message)
        await ctx.send(response_text)

    @slash.slash(
        name="yell",
        description="Have Botto yell at someone",
        options=[
            person_option("The person to yell at.", False),
            message_option,
        ],
        # guild_ids=[833842753799848016],
    )
    async def yell(ctx: SlashContext, person: str, **kwargs):
        await _yell(ctx, person, **kwargs)

    @slash.slash(
        name="yellat",
        description="Have Botto yell at someone (with selection)",
        options=[
            person_option("The person to yell at.", True),
            message_option,
        ],
        # guild_ids=[833842753799848016],
    )
    async def yell_at(ctx: SlashContext, person: discord.Member, **kwargs):
        await _yell(ctx, person, **kwargs)

    def _local_times(time_now: datetime = datetime.utcnow()) -> list[datetime]:
        return [time_now.astimezone(zone) for zone in config["timezones"]]

    @slash.slash(
        name="times",
        description="Get the current times for TLDers",
        options=[
            create_option(
                name="current_time",
                description="The time to use as 'now'.",
                option_type=SlashCommandOptionType.STRING,
                required=False,
            )
        ],
        # guild_ids=[833842753799848016],
    )
    async def send_local_times(ctx: SlashContext, **kwargs):
        parsed_time = datetime.utcnow()
        current_time = kwargs.get("current_time")
        if current_time:
            try:
                parsed_time = dateparser.parse(current_time)
            except ValueError as error:
                await ctx.send(f"Failed to parse provided time: {error}")

        log.debug(f"/times from: {ctx.author} relative to {parsed_time}")
        local_times_string = responses.get_local_times(
            local_times=_local_times(parsed_time)
        )
        converted_string = f"{current_time} converted:\n" if current_time else ""
        await ctx.send(converted_string + local_times_string)

    @slash.slash(
        name="reminder",
        description="Set a reminder",
        options=[
            create_option(
                name="at",
                description="The date/time of the reminder.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
            create_option(
                name="message",
                description="The message associated with the reminder.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
            create_option(
                name="advance_warning",
                description="Should Tildy send a 15 minute advance warning?",
                option_type=SlashCommandOptionType.BOOLEAN,
                required=False,
            ),
            create_option(
                name="channel",
                description="What channel should Tildy send a message to? (Defaults to the current one)",
                option_type=SlashCommandOptionType.CHANNEL,
                required=False,
            ),
        ],
        # guild_ids=[833842753799848016],
    )
    async def reminder(ctx: SlashContext, at: str, message: str, **kwargs):
        try:
            advance_warning = kwargs.get("advance_warning") is True
            channel: discord.TextChannel = kwargs.get("channel") or ctx.channel
            log.debug(
                f"/reminder from: {ctx.author} at: {at}, advance warning: {advance_warning}, channel: {channel}"
            )
            created_reminder = await reminder_manager.add_reminder_slash(
                ctx.author, at, message, channel, advance_reminder=advance_warning
            )
            reminder_message = await reminder_manager.build_reminder_message(
                created_reminder
            )
            await ctx.send(reminder_message)
        except TimeTravelError as error:
            log.error("Reminder request expected time travel")
            await ctx.send(error.message, hidden=True)
        except ReminderParsingError:
            log.error("Failed to process reminder time", exc_info=True)
            await ctx.send(
                f"I'm sorry, I was unable to process this time 😢.", hidden=True
            )

    @slash.slash(
        name="unixtime",
        description="Covert a timestamp to Unix Time and display it to you (only)",
        options=[
            create_option(
                name="timestamp",
                description="The date/time of the reminder.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            )
        ],
        # guild_ids=[833842753799848016],
    )
    async def unix_time(ctx: SlashContext, timestamp: str):
        try:
            log.debug(f"/unixtime from: {ctx.author} timestamp: {timestamp}")
            parsed_date = dateparser.parse(timestamp)
        except (ValueError, OverflowError):
            log.error(f"Failed to parse date: {timestamp}", exc_info=True)
            await ctx.send("Sorry, I was unable to parse that time", hidden=True)
            return
        unix_timestamp = round(parsed_date.timestamp())
        await ctx.send(
            f"{timestamp} (parsed as `{parsed_date}`) is `{unix_timestamp}` in Unix Time",
            hidden=True,
        )

    @slash.slash(
        name="time",
        description="Display a time using `<t:>",
        options=[
            create_option(
                name="timestamp",
                description="Sends a response displaying this timestamp in everyone's local time.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            )
        ],
        # guild_ids=[833842753799848016],
    )
    async def time(ctx: SlashContext, timestamp: str):
        try:
            log.debug(f"/time from: {ctx.author} timestamp: {timestamp}")
            parsed_date = dateparser.parse(timestamp)
        except (ValueError, OverflowError):
            log.error(f"Failed to parse date: {timestamp}", exc_info=True)
            await ctx.send("Sorry, I was unable to parse that time", hidden=True)
            return
        unix_timestamp = round(parsed_date.timestamp())
        await ctx.send(
            f"{timestamp} (parsed as `{parsed_date}`) is <t:{unix_timestamp}> (<t:{unix_timestamp}:R>)"
        )

    async def _get_timezone(discord_id: str) -> Timezone:
        tlder = await timezones.get_tlder(discord_id)
        if tlder is None:
            raise TlderNotFoundError(discord_id)
        timezone = await timezones.get_timezone(tlder.timezone_id)
        return timezone

    @slash.subcommand(
        base="timezones",
        subcommand_group="get",
        subcommand_group_description="Get details of configured timezones",
        name="current",
        description="Get your timezone",
        # guild_ids=[880491989995499600, 833842753799848016],
    )
    async def get_timezone(ctx: SlashContext):
        log.debug(f"/timezones get current from {ctx.author}")
        try:
            timezone = await _get_timezone(ctx.author_id)
            await ctx.send(
                "Your currently configured timezone is: {timezone_name} (UTC{offset})".format(
                    timezone_name=timezone.name,
                    offset=arrow.now(timezone.name).format("Z"),
                ),
                hidden=True,
            )
        except TlderNotFoundError:
            log.info(f"{ctx.author} has not configured timezone")
            await ctx.send("Sorry, you don't have a timezone configured 😢", hidden=True)
            return

    @slash.subcommand(
        base="timezones",
        subcommand_group="get",
        subcommand_group_description="Get details of configured timezones",
        name="user",
        description="Get the user's timezone",
        options=[person_option("The user for whom to get the timezone", True)]
        # guild_ids=[880491989995499600, 833842753799848016],
    )
    async def get_user_timezone(ctx: SlashContext, person: discord.Member):
        log.debug(f"/timezones get user from {ctx.author} for {person}")
        try:
            timezone = await _get_timezone(person.id)
            await ctx.send(
                "{person_name}'s currently configured timezone is: {timezone_name} (UTC{offset})".format(
                    person_name=person.display_name,
                    timezone_name=timezone.name,
                    offset=arrow.now(timezone.name).format("Z"),
                )
            )
        except TlderNotFoundError:
            log.info(f"{person} has not configured a timezone")
            await ctx.send(
                f"{person.display_name} does not appear to have a timezone configured"
            )
            return

    @slash.subcommand(
        base="timezones",
        name="set",
        description="Set your timezone. Must be an identifier in the TZ Database.",
        options=[
            create_option(
                name="timezone_name",
                description="Timezone name, as it appears in the TZ Database.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            )
        ],
        # guild_ids=[880491989995499600, 833842753799848016],
    )
    async def set_my_timezone(ctx: SlashContext, timezone_name: str):
        log.debug(f"/timezones set from {ctx.author} for timezone name {timezone_name}")
        tzinfo: pytz.tzinfo
        try:
            tzinfo = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            await ctx.send(
                f"Sorry, {timezone_name} is not a known TZ DB key", hidden=True
            )
            return
        get_tlder_request = timezones.get_tlder(ctx.author_id)
        db_timezone = await timezones.find_timezone(tzinfo.zone)
        if db_timezone is None:
            log.info(f"{tzinfo.zone} not found, adding new timezone")
            db_timezone = await timezones.add_timezone(tzinfo.zone)
        if tlder := await get_tlder_request:
            log.info("Updating existing TLDer's timezone")
            try:
                await timezones.update_tlder(tlder, timezone_id=db_timezone.id)
            except AirTableError:
                log.error(f"Failed to update TLDer", exc_info=True)
                await ctx.send(
                    "Internal error updating TLDer {dizzy}".format(
                        dizzy=config["reactions"]["dizzy"]
                    )
                )
                return
        else:
            log.info("Adding new TLDer with timezone")
            await timezones.add_tlder(ctx.author.name, str(ctx.author.id), db_timezone.id)
        await ctx.send(
            "Your timezone has been set to: {timezone_name} (UTC{offset})".format(
                timezone_name=db_timezone.name,
                offset=arrow.now(db_timezone.name).format("Z"),
            ),
            hidden=True,
        )

    return slash
