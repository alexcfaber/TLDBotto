import asyncio
import logging
from typing import Union, Optional, TYPE_CHECKING

import discord
from discord import Message

if TYPE_CHECKING:
    from tld_botto import TLDBotto

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


async def remove_user_reactions(
    message: Message, user: Union[discord.abc.User, discord.ClientUser]
):
    """
    Removes all reactions by the user from the message.
    :param message: The message from which to remove reactions
    :param user: The user for which reactions should be removed
    """
    log.info(f"Removing reactions by {user} from {message}")
    my_reactions = [r for r in message.reactions if any(u.id == user.id async for u in r.users())]
    clearing_reactions = [message.remove_reaction(r.emoji, user) for r in my_reactions]
    await asyncio.wait(clearing_reactions)


async def remove_own_message(
    requester_name: str, message: Message, delay: Optional[int] = None
):
    log.info(
        "{requester_name} triggered deletion of our message (id: {message_id} in {channel_name}): {content}".format(
            requester_name=requester_name,
            message_id=message.id,
            channel_name=message.channel.name,
            content=message.content,
        )
    )
    if delay:
        await message.delete(delay=delay)
    else:
        await message.delete()


async def resolve_message_reference(
    bot: "TLDBotto", message: Message, force_fresh: bool = False
) -> Message:
    if not message.reference:
        raise MessageMissingReferenceError(message)

    if not force_fresh:
        if referenced_message := message.reference.resolved:
            return referenced_message

    reference_channel = await bot.get_or_fetch_channel(message.reference.channel_id)

    referenced_message = await reference_channel.fetch_message(
        message.reference.message_id
    )
    return referenced_message


def is_voting_message(message: Message) -> bool:
    return message.content.lstrip().startswith("🗳️")


def guild_member_count(message: Message) -> int:
    return len([member for member in message.guild.members if not member.bot])


class MessageMissingReferenceError(Exception):
    def __init__(self, message: Message, *args: object) -> None:
        self.message = message
        super().__init__(*args)
