import discord
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from botto.reactions import Reactions
from botto.reminder_manager import ReminderManager
from botto.slash_commands import setup_slash
from botto.storage import AirtableMealStorage, ReminderStorage, TimezoneStorage, EnablementStorage
from botto.tld_botto import TLDBotto


def test_startup():
    scheduler = AsyncIOScheduler()

    storage = AirtableMealStorage(
        "fake_base", "fake_key"
    )

    reminder_storage = ReminderStorage(
        "fake_base", "fake_key"
    )

    timezone_storage = TimezoneStorage(
        "fake_base", "fake_key"
    )

    enablement_storage = EnablementStorage(
        "fake_base", "fake_key"
    )

    reactions = Reactions({})
    reminder_manager = ReminderManager({}, scheduler, reminder_storage, reactions, timezone_storage)

    client = TLDBotto({}, reactions, scheduler, storage, timezone_storage, reminder_manager, enablement_storage)
    slash = setup_slash(client, {}, reminder_manager, timezone_storage)
    with pytest.raises(discord.LoginFailure):
        client.run("fake_discord_key")