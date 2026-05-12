"""
Calendar tools — list, create, and manage Google Calendar events.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from googleapiclient.discovery import build
from .google_auth import get_google_credentials


class CalendarTools:
    def __init__(self):
        creds = get_google_credentials()
        self.service = build("calendar", "v3", credentials=creds)

    DAVE_KAT_CALENDAR = "mo5p83s0mpe2diotk596v57c04@group.calendar.google.com"

    def list_calendars(self) -> list[dict]:
        result = self.service.calendarList().list().execute()
        return [
            {
                "id": cal["id"],
                "summary": cal.get("summary", ""),
                "primary": cal.get("primary", False),
                "access_role": cal.get("accessRole", ""),
            }
            for cal in result.get("items", [])
        ]

    def list_events(self, days_ahead: int = 7, max_results: int = 20, calendar_id: str = None) -> list[dict]:
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)
        results = self.service.events().list(
            calendarId=calendar_id, timeMin=now.isoformat(), timeMax=time_max.isoformat(),
            maxResults=max_results, singleEvents=True, orderBy="startTime",
        ).execute()
        return [self._format_event(e) for e in results.get("items", [])]

    def list_events_range(self, time_min: str, time_max: str, max_results: int = 50,
                          calendar_id: str = None) -> list[dict]:
        """List events between two ISO 8601 timestamps."""
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        results = self.service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            maxResults=max_results, singleEvents=True, orderBy="startTime",
        ).execute()
        return [self._format_event(e) for e in results.get("items", [])]

    def get_todays_events(self, calendar_id: str = None) -> list[dict]:
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        results = self.service.events().list(
            calendarId=calendar_id, timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime",
        ).execute()
        return [self._format_event(e) for e in results.get("items", [])]

    def create_event(self, summary: str, start: str, end: str, description: str = "",
                     location: str = "", attendees: Optional[list[str]] = None,
                     calendar_id: str = None) -> dict:
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        event_body = {
            "summary": summary, "description": description, "location": location,
            "start": {"dateTime": start}, "end": {"dateTime": end},
        }
        if attendees:
            event_body["attendees"] = [{"email": e} for e in attendees]
        result = self.service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return {
            "action": "created", "id": result["id"], "summary": result.get("summary"),
            "start": result["start"].get("dateTime", result["start"].get("date")),
            "end": result["end"].get("dateTime", result["end"].get("date")),
            "link": result.get("htmlLink", ""),
        }

    def quick_add(self, text: str, calendar_id: str = None) -> dict:
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        result = self.service.events().quickAdd(calendarId=calendar_id, text=text).execute()
        return {
            "action": "quick_added", "id": result["id"],
            "summary": result.get("summary", text),
            "start": result.get("start", {}).get("dateTime", result.get("start", {}).get("date")),
            "link": result.get("htmlLink", ""),
        }

    def delete_event(self, event_id: str, calendar_id: str = None) -> dict:
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"action": "deleted", "event_id": event_id}

    def check_free_busy(self, start: str, end: str, calendar_id: str = None) -> dict:
        if calendar_id is None:
            calendar_id = self.DAVE_KAT_CALENDAR
        body = {"timeMin": start, "timeMax": end, "items": [{"id": calendar_id}]}
        result = self.service.freebusy().query(body=body).execute()
        busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return {"is_free": len(busy) == 0, "busy_periods": busy, "checked_range": {"start": start, "end": end}}

    @staticmethod
    def _format_event(event: dict) -> dict:
        start = event.get("start", {})
        end = event.get("end", {})
        return {
            "id": event["id"], "summary": event.get("summary", "(no title)"),
            "start": start.get("dateTime", start.get("date", "")),
            "end": end.get("dateTime", end.get("date", "")),
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "link": event.get("htmlLink", ""),
            "is_all_day": "date" in start and "dateTime" not in start,
        }
