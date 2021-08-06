from collections import namedtuple
from dataclasses import dataclass
from datetime import time, datetime
from typing import Union

from yarl import URL


@dataclass
class Intro:
    texts: list[str]

    @classmethod
    def from_airtable(cls, data: dict) -> "Intro":
        fields = data["fields"]
        return cls(
            texts=fields.get("Texts"),
        )


@dataclass
class Meal:
    name: str
    start: time
    end: time
    texts: list[str]
    emoji: str

    @classmethod
    def from_airtable(cls, data: dict) -> "Meal":
        fields = data["fields"]
        start_time = fields.get("Start Time")
        end_time = fields.get("End Time")
        return cls(
            name=fields.get("Name"),
            start=datetime.strptime(start_time, "%H:%M").time() if start_time else None,
            end=datetime.strptime(end_time, "%H:%M").time() if end_time else None,
            texts=fields.get("Texts"),
            emoji=fields.get("Emoji"),
        )


@dataclass
class Reminder:
    id: str
    date: datetime
    notes: str
    remind_15_minutes_before: bool
    msg_id: str
    channel_id: str

    @classmethod
    def from_airtable(cls, data: dict) -> "Reminder":
        fields = data["fields"]
        date_sting = fields.get("Date")
        parsed_date = datetime.strptime(date_sting, "%Y-%m-%dT%H:%M:%S.%f%z")
        note = fields.get("Notes")
        advance_reminder = fields.get("15 Minutes Before")
        msg_id = fields.get("Message ID")
        channel_id = fields.get("Channel ID")
        return cls(
            id=data["id"],
            date=parsed_date,
            notes=note,
            remind_15_minutes_before=advance_reminder,
            msg_id=msg_id,
            channel_id=channel_id,
        )

    def to_airtable(self, fields=None) -> dict:
        fields = fields if fields else ["id", "date", "notes"]
        data = {}
        if "date" in fields:
            data["Date"] = self.date.isoformat()
        if "notes" in fields:
            data["Notes"] = self.notes
        return {
            "id": self.id,
            "fields": data,
        }


MessageAndChannel = namedtuple("MessageAndChannel", ["channel_id", "msg_id"])


@dataclass
class TLDer:
    id: str
    discord_id: str
    name: str
    timezone_id: str

    @classmethod
    def from_airtable(cls, data: dict) -> "TLDer":
        fields = data["fields"]
        return cls(
            id=data["id"],
            discord_id=fields.get("Discord ID"),
            name=fields.get("Name"),
            timezone_id=fields["Timezone"][0] if fields.get("Timezone") else None,
        )


@dataclass
class Timezone:
    id: str
    name: str

    @classmethod
    def from_airtable(cls, data: dict) -> "Timezone":
        fields = data["fields"]
        return cls(
            id=data["id"],
            name=fields.get("Name"),
        )


@dataclass
class Enablement:
    name: str
    enabled_item: str
    enabled_by: str
    date: datetime

    @classmethod
    def from_airtable(cls, data: dict) -> "Enablement":
        fields = data["fields"]
        return cls(
            name=fields.get("Name"),
            enabled_item=fields.get("Enabled"),
            enabled_by=fields.get("Enabled By"),
            date=fields.get("Date"),
        )


class AirTableError(Exception):
    def __init__(
            self, url: URL, response_dict: Union[dict, str], *args: object
    ) -> None:
        error_dict: dict = response_dict["error"]
        self.url = url
        if type(error_dict) is dict:
            self.error_type = error_dict.get("type")
            self.error_message = error_dict.get("message")
        else:
            self.error_type = error_dict
            self.error_message = ""
        super().__init__(*args)

    def __repr__(self) -> str:
        return "{class_name}(type:{error_type}, message:'{error_message}', url:{url})".format(
            class_name=self.__class__,
            error_type=self.error_type,
            error_message=self.error_message,
            url=self.url,
        )

    def __str__(self) -> str:
        return "Error from AirTable operation of type '{error_type}', with message:'{error_message}'. Request URL: {url}".format(
            error_type=self.error_type, error_message=self.error_message, url=self.url
        )
