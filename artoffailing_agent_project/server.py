"""
Workstation Agent — MCP Server

A personal assistant MCP server that gives GitHub Copilot access to
local files, Gmail, and Google Calendar via stdio transport.

Run: python server.py
Or let VS Code start it automatically via .vscode/mcp.json
"""

import os
import sys
import json
import logging
import secrets
import argparse
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from tools.file_tools import FileTools
from tools.gmail_tools import GmailTools
from tools.calendar_tools import CalendarTools
from tools.context_memory import ContextMemory, register_context_memory
from tools.daily_briefing import register_daily_briefing
from tools.daily_digest import register_daily_digest
from tools.daily_notes import register_daily_notes
from tools.focus_timer import register_focus_timer
from tools.iracing_tools import register_iracing_tools
from tools.iracing_api import register_iracing_api
from tools.notes_tool import register_notes_tools
from tools.weekly_review import register_weekly_review
from tools.jira_tools import JiraTools
from tools.meeting_notes import MeetingNotes
from tools.news_tools import NewsTools
from tools.weather_tools import WeatherTools
from tools.work_journal import WorkJournal
from tools.blog_tools import BlogTools, JekyllExpert, BlogWriter
from tools.codedoc_tools import CodeDocumentor
from tools.spotify_tools import SpotifyAuth, SpotifyTools
from tools.network_tools import register_network_tools
from tools.price_search import register_price_search
from tools.reminders import register_reminders
from tools.car_rental_tools import register_car_rental_tools

load_dotenv()

# Logging goes to stderr — stdout is reserved for MCP protocol messages
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("workstation-agent")

# ── Initialize MCP server ───────────────────────────────────────────

mcp = FastMCP("workstation-agent")

# ── Tool instances (lazy-loaded for Google tools) ────────────────────

file_tools = FileTools(root=os.getenv("FILE_TOOLS_ROOT", "~/Documents"))
_gmail: Optional[GmailTools] = None
_calendar: Optional[CalendarTools] = None


def get_gmail() -> GmailTools:
    global _gmail
    if _gmail is None:
        _gmail = GmailTools()
    return _gmail


def get_calendar() -> CalendarTools:
    global _calendar
    if _calendar is None:
        _calendar = CalendarTools()
    return _calendar


# ── Class-based tool instances ───────────────────────────────────────

_jira = JiraTools()
_meetings = MeetingNotes()
_news = NewsTools()
_weather = WeatherTools()
_journal = WorkJournal()
_blog = BlogTools()
_jekyll = JekyllExpert()
_blog_writer = BlogWriter()
_codedoc = CodeDocumentor()
_spotify_auth = SpotifyAuth()
_spotify: Optional[SpotifyTools] = None
_context_memory = ContextMemory()


def get_spotify() -> SpotifyTools:
    global _spotify
    if _spotify is None:
        _spotify = SpotifyTools(_spotify_auth)
    return _spotify

# ── Register function-based tools ────────────────────────────────────

register_context_memory(mcp, _context_memory)
register_daily_briefing(mcp, gmail_client=get_gmail, gcal_client=get_calendar, context_memory=_context_memory)
register_daily_digest(mcp, context_memory=_context_memory)
register_daily_notes(mcp)
register_focus_timer(mcp)
register_iracing_tools(mcp)
register_iracing_api(mcp)
register_network_tools(mcp)
register_notes_tools(mcp)
register_weekly_review(mcp, gcal_client=get_calendar, context_memory=_context_memory)
register_price_search(mcp)
register_reminders(mcp)
register_car_rental_tools(mcp)


# ════════════════════════════════════════════════════════════════════
#  SPOTIFY TOOLS
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def spotify_auth_url() -> str:
    """Get the Spotify authorization URL. Open this in a browser to authenticate."""
    if not _spotify_auth.is_configured:
        return (
            "Spotify not configured. Create a Spotify Developer app at "
            "https://developer.spotify.com/dashboard and save your client_id "
            "and client_secret to config/spotify_credentials.json"
        )
    return _spotify_auth.get_auth_url()


@mcp.tool()
def spotify_authorize() -> str:
    """Authenticate with Spotify interactively. Opens browser, captures callback automatically."""
    try:
        result = _spotify_auth.authorize_interactive()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def spotify_auth_callback(code: str) -> str:
    """Complete Spotify authentication with the authorization code from the redirect URL.

    After visiting the auth URL, Spotify redirects to localhost with a ?code= parameter.
    Paste that code here to finish authentication.
    """
    try:
        result = _spotify_auth.exchange_code(code)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def spotify_now_playing() -> str:
    """Get the currently playing track on Spotify."""
    return json.dumps(get_spotify().now_playing(), indent=2)


@mcp.tool()
def spotify_play(uri: str = "", device_id: str = "") -> str:
    """Start or resume Spotify playback.

    Args:
        uri: Optional Spotify URI to play (track, album, artist, or playlist).
             Examples: 'spotify:track:6rqhFgbbKwnb9MLmUQDhG6',
             'spotify:album:...', 'spotify:playlist:...'
             Leave empty to resume current playback.
        device_id: Optional device ID to play on. Use spotify_devices() to list.
    """
    return json.dumps(get_spotify().play(uri, device_id), indent=2)


@mcp.tool()
def spotify_pause() -> str:
    """Pause Spotify playback."""
    return json.dumps(get_spotify().pause(), indent=2)


@mcp.tool()
def spotify_next() -> str:
    """Skip to the next track."""
    return json.dumps(get_spotify().next_track(), indent=2)


@mcp.tool()
def spotify_previous() -> str:
    """Skip to the previous track."""
    return json.dumps(get_spotify().previous_track(), indent=2)


@mcp.tool()
def spotify_volume(volume_percent: int) -> str:
    """Set Spotify playback volume.

    Args:
        volume_percent: Volume level from 0 to 100.
    """
    return json.dumps(get_spotify().set_volume(volume_percent), indent=2)


@mcp.tool()
def spotify_shuffle(state: bool) -> str:
    """Toggle shuffle mode.

    Args:
        state: True to enable shuffle, False to disable.
    """
    return json.dumps(get_spotify().shuffle(state), indent=2)


@mcp.tool()
def spotify_repeat(state: str = "off") -> str:
    """Set repeat mode.

    Args:
        state: 'track' to repeat the current track, 'context' to repeat
               the album/playlist, or 'off' to disable repeat.
    """
    return json.dumps(get_spotify().repeat(state), indent=2)


@mcp.tool()
def spotify_queue(uri: str) -> str:
    """Add a track to the end of the playback queue.

    Args:
        uri: Spotify URI of the track to queue (e.g. 'spotify:track:...').
    """
    return json.dumps(get_spotify().queue_track(uri), indent=2)


@mcp.tool()
def spotify_get_queue() -> str:
    """Get the current playback queue (up to 20 upcoming tracks)."""
    return json.dumps(get_spotify().get_queue(), indent=2)


@mcp.tool()
def spotify_devices() -> str:
    """List available Spotify playback devices."""
    return json.dumps(get_spotify().get_devices(), indent=2)


@mcp.tool()
def spotify_transfer(device_id: str) -> str:
    """Transfer playback to a different device.

    Args:
        device_id: The device ID to transfer to. Use spotify_devices() to find IDs.
    """
    return json.dumps(get_spotify().transfer_playback(device_id), indent=2)


@mcp.tool()
def spotify_search(query: str, search_type: str = "track", limit: int = 10) -> str:
    """Search Spotify for tracks, artists, albums, or playlists.

    Args:
        query: Search query (e.g. 'Radiohead', 'In Rainbows', 'jazz focus').
        search_type: One of 'track', 'artist', 'album', 'playlist'.
        limit: Max results (1-50, default 10).
    """
    return json.dumps(get_spotify().search(query, search_type, limit), indent=2)


@mcp.tool()
def spotify_playlists(limit: int = 20) -> str:
    """List your Spotify playlists.

    Args:
        limit: Max playlists to return (1-50, default 20).
    """
    return json.dumps(get_spotify().list_playlists(limit), indent=2)


@mcp.tool()
def spotify_playlist_tracks(playlist_id: str, limit: int = 50) -> str:
    """Get tracks from a Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID (from spotify_playlists).
        limit: Max tracks to return (1-100, default 50).
    """
    return json.dumps(get_spotify().get_playlist_tracks(playlist_id, limit), indent=2)


@mcp.tool()
def spotify_create_playlist(name: str, description: str = "", public: bool = False) -> str:
    """Create a new Spotify playlist.

    Args:
        name: Playlist name.
        description: Optional playlist description.
        public: Whether the playlist should be public (default False).
    """
    return json.dumps(get_spotify().create_playlist(name, description, public), indent=2)


@mcp.tool()
def spotify_add_to_playlist(playlist_id: str, uris: str) -> str:
    """Add tracks to a Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID.
        uris: Comma-separated Spotify track URIs to add.
    """
    uri_list = [u.strip() for u in uris.split(",") if u.strip()]
    return json.dumps(get_spotify().add_to_playlist(playlist_id, uri_list), indent=2)


@mcp.tool()
def spotify_remove_from_playlist(playlist_id: str, uris: str) -> str:
    """Remove tracks from a Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID.
        uris: Comma-separated Spotify track URIs to remove.
    """
    uri_list = [u.strip() for u in uris.split(",") if u.strip()]
    return json.dumps(get_spotify().remove_from_playlist(playlist_id, uri_list), indent=2)


@mcp.tool()
def spotify_recently_played(limit: int = 20) -> str:
    """Get your recently played tracks.

    Args:
        limit: Max tracks to return (1-50, default 20).
    """
    return json.dumps(get_spotify().recently_played(limit), indent=2)


@mcp.tool()
def spotify_top_tracks(time_range: str = "medium_term", limit: int = 20) -> str:
    """Get your top tracks on Spotify.

    Args:
        time_range: 'short_term' (last 4 weeks), 'medium_term' (last 6 months),
                    'long_term' (all time). Default 'medium_term'.
        limit: Max tracks to return (1-50, default 20).
    """
    return json.dumps(get_spotify().top_tracks(time_range, limit), indent=2)


@mcp.tool()
def spotify_top_artists(time_range: str = "medium_term", limit: int = 20) -> str:
    """Get your top artists on Spotify.

    Args:
        time_range: 'short_term' (last 4 weeks), 'medium_term' (last 6 months),
                    'long_term' (all time). Default 'medium_term'.
        limit: Max artists to return (1-50, default 20).
    """
    return json.dumps(get_spotify().top_artists(time_range, limit), indent=2)


@mcp.tool()
def spotify_save_tracks(track_ids: str) -> str:
    """Save tracks to your Spotify library (Like).

    Args:
        track_ids: Comma-separated Spotify track IDs (not full URIs).
    """
    ids = [t.strip() for t in track_ids.split(",") if t.strip()]
    return json.dumps(get_spotify().save_tracks(ids), indent=2)


@mcp.tool()
def spotify_remove_saved_tracks(track_ids: str) -> str:
    """Remove tracks from your Spotify library (Unlike).

    Args:
        track_ids: Comma-separated Spotify track IDs (not full URIs).
    """
    ids = [t.strip() for t in track_ids.split(",") if t.strip()]
    return json.dumps(get_spotify().remove_saved_tracks(ids), indent=2)


# ════════════════════════════════════════════════════════════════════
#  FILE TOOLS
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_directory(path: str = ".", show_hidden: bool = False) -> str:
    """List files and folders at a path. Returns name, type, size, and modified date."""
    items = file_tools.list_dir(path, show_hidden)
    return json.dumps(items, indent=2)


@mcp.tool()
def directory_tree(path: str = ".", max_depth: int = 3) -> str:
    """Show a text tree view of the directory structure."""
    return file_tools.tree(path, max_depth)


@mcp.tool()
def file_info(path: str) -> str:
    """Get detailed information about a specific file or directory."""
    return json.dumps(file_tools.file_info(path), indent=2)


@mcp.tool()
def move_file(source: str, destination: str) -> str:
    """Move a file or directory to a new location."""
    return json.dumps(file_tools.move(source, destination), indent=2)


@mcp.tool()
def rename_file(path: str, new_name: str) -> str:
    """Rename a file or directory (stays in the same parent folder)."""
    return json.dumps(file_tools.rename(path, new_name), indent=2)


@mcp.tool()
def copy_file(source: str, destination: str) -> str:
    """Copy a file or directory to a new location."""
    return json.dumps(file_tools.copy(source, destination), indent=2)


@mcp.tool()
def create_directory(path: str) -> str:
    """Create a new directory and any missing parent directories."""
    return json.dumps(file_tools.mkdir(path), indent=2)


@mcp.tool()
def delete_file(path: str) -> str:
    """Delete a file or empty directory. Refuses to delete non-empty directories."""
    return json.dumps(file_tools.delete(path), indent=2)


@mcp.tool()
def find_files(pattern: str = "*", path: str = ".", max_results: int = 50) -> str:
    """Search for files matching a glob pattern (e.g. '*.pdf', 'report*'). Recursive."""
    results = file_tools.find_files(pattern, path, max_results)
    return json.dumps(results, indent=2)


@mcp.tool()
def search_file_contents(query: str, path: str = ".", max_results: int = 20) -> str:
    """Search inside text files for a string. Case-insensitive. Returns matching files with line context."""
    results = file_tools.search_content(query, path, max_results=max_results)
    return json.dumps(results, indent=2)


@mcp.tool()
def organize_by_extension(path: str = ".") -> str:
    """Organize files into subdirectories by extension (e.g. .pdf → pdf/). Top-level only."""
    return json.dumps(file_tools.organize_by_extension(path), indent=2)


# ════════════════════════════════════════════════════════════════════
#  GMAIL TOOLS
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_emails(query: str = "", max_results: int = 10, label: str = "INBOX") -> str:
    """List recent emails. Supports up to 500 results with automatic pagination.
    Use Gmail search syntax for filtering (e.g. 'from:boss@co.com', 'is:unread', 'subject:invoice').
    Returns messages plus a next_page_token if more results are available."""
    result = get_gmail().list_messages(query, max_results, label)
    return json.dumps(result, indent=2)


@mcp.tool()
def read_email(message_id: str) -> str:
    """Read the full body of an email by its message ID."""
    return json.dumps(get_gmail().read_message(message_id), indent=2)


@mcp.tool()
def unread_email_count() -> str:
    """Get the number of unread emails in the inbox."""
    count = get_gmail().get_unread_count()
    return json.dumps({"unread": count})


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Send a plain text email."""
    return json.dumps(get_gmail().send_email(to, subject, body), indent=2)


@mcp.tool()
def create_email_draft(to: str, subject: str, body: str) -> str:
    """Create a draft email without sending it."""
    return json.dumps(get_gmail().create_draft(to, subject, body), indent=2)


@mcp.tool()
def list_gmail_labels() -> str:
    """List all Gmail labels with message counts."""
    labels = get_gmail().list_labels()
    return json.dumps(labels, indent=2)


@mcp.tool()
def create_gmail_label(name: str) -> str:
    """Create a new Gmail label."""
    return json.dumps(get_gmail().create_label(name), indent=2)


@mcp.tool()
def delete_gmail_label(label_id: str) -> str:
    """Delete a user-created Gmail label by its ID. System labels cannot be deleted."""
    return json.dumps(get_gmail().delete_label(label_id), indent=2)


@mcp.tool()
def rename_gmail_label(label_id: str, new_name: str) -> str:
    """Rename an existing Gmail label."""
    return json.dumps(get_gmail().rename_label(label_id, new_name), indent=2)


@mcp.tool()
def modify_message_labels(message_id: str, add_label_ids: str = "", remove_label_ids: str = "") -> str:
    """Add or remove labels from a single message. Provide comma-separated label IDs."""
    add = [lid.strip() for lid in add_label_ids.split(",") if lid.strip()] if add_label_ids else None
    remove = [lid.strip() for lid in remove_label_ids.split(",") if lid.strip()] if remove_label_ids else None
    return json.dumps(get_gmail().modify_message_labels(message_id, add, remove), indent=2)


@mcp.tool()
def batch_modify_labels(message_ids: str, add_label_ids: str = "", remove_label_ids: str = "") -> str:
    """
    Add or remove labels from multiple messages at once.
    message_ids: comma-separated list of message IDs.
    add_label_ids / remove_label_ids: comma-separated Gmail label IDs (e.g. 'TRASH', 'INBOX', 'UNREAD').
    Use label ID 'TRASH' to move messages to Trash.
    """
    ids = [mid.strip() for mid in message_ids.split(",") if mid.strip()]
    add = [lid.strip() for lid in add_label_ids.split(",") if lid.strip()] if add_label_ids else None
    remove = [lid.strip() for lid in remove_label_ids.split(",") if lid.strip()] if remove_label_ids else None
    return json.dumps(get_gmail().batch_modify_labels(ids, add, remove), indent=2)



@mcp.tool()
def bulk_organize_emails(operations_json: str) -> str:
    """Apply multiple label operations to emails in a single call.

    Takes a JSON array of operations. Each operation has:
      - message_ids: comma-separated message IDs
      - add_labels: comma-separated label IDs to add (e.g. 'TRASH', 'CATEGORY_UPDATES')
      - remove_labels: comma-separated label IDs to remove (e.g. 'INBOX', 'UNREAD')

    Example operations_json:
    [
      {"message_ids": "id1,id2,id3", "add_labels": "TRASH", "remove_labels": "INBOX,UNREAD"},
      {"message_ids": "id4,id5", "add_labels": "CATEGORY_UPDATES", "remove_labels": "UNREAD"},
      {"message_ids": "id6", "add_labels": "CATEGORY_SOCIAL", "remove_labels": "UNREAD"}
    ]
    """
    ops = json.loads(operations_json)
    parsed = []
    for op in ops:
        ids_raw = op.get("message_ids", "")
        add_raw = op.get("add_labels", "")
        remove_raw = op.get("remove_labels", "")
        parsed.append({
            "message_ids": [mid.strip() for mid in ids_raw.split(",") if mid.strip()],
            "add_labels": [lid.strip() for lid in add_raw.split(",") if lid.strip()] if add_raw else None,
            "remove_labels": [lid.strip() for lid in remove_raw.split(",") if lid.strip()] if remove_raw else None,
        })
    return json.dumps(get_gmail().bulk_organize(parsed), indent=2)


# ════════════════════════════════════════════════════════════════════
#  CALENDAR TOOLS
# ════════════════════════════════════════════════════════════════════

DEFAULT_CALENDAR_ID = "mo5p83s0mpe2diotk596v57c04@group.calendar.google.com"  # replace with your calendar ID from Google Calendar settings

@mcp.tool()
def list_calendars() -> str:
    """List all Google Calendars the authenticated account can access."""
    calendars = get_calendar().list_calendars()
    return json.dumps(calendars, indent=2)


@mcp.tool()
def list_calendar_events(days_ahead: int = 7, max_results: int = 20) -> str:
    """List upcoming calendar events for the next N days."""
    events = get_calendar().list_events(days_ahead, max_results, calendar_id=DEFAULT_CALENDAR_ID)
    return json.dumps(events, indent=2)


@mcp.tool()
def todays_events() -> str:
    """Get all calendar events happening today."""
    events = get_calendar().get_todays_events(calendar_id=DEFAULT_CALENDAR_ID)
    return json.dumps(events, indent=2)


@mcp.tool()
def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
) -> str:
    """Create a new calendar event. Start/end must be ISO 8601 format (e.g. '2026-04-01T10:00:00-04:00')."""
    result = get_calendar().create_event(summary, start, end, description, location, calendar_id=DEFAULT_CALENDAR_ID)
    return json.dumps(result, indent=2)


@mcp.tool()
def quick_add_event(text: str) -> str:
    """Create an event using natural language (e.g. 'Lunch with Sarah tomorrow at noon')."""
    return json.dumps(get_calendar().quick_add(text, calendar_id=DEFAULT_CALENDAR_ID), indent=2)


@mcp.tool()
def delete_calendar_event(event_id: str) -> str:
    """Delete a calendar event by its event ID."""
    return json.dumps(get_calendar().delete_event(event_id, calendar_id=DEFAULT_CALENDAR_ID), indent=2)


@mcp.tool()
def check_availability(start: str, end: str) -> str:
    """Check if a time range is free or has conflicts. Times in ISO 8601 format."""
    return json.dumps(get_calendar().check_free_busy(start, end, calendar_id=DEFAULT_CALENDAR_ID), indent=2)


# ════════════════════════════════════════════════════════════════════
#  JIRA TOOLS
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def jira_create_ticket(
    title: str,
    description: str,
    scope: str = "",
    exit_criteria: str = "",
    ticket_type: str = "Story",
    priority: str = "Medium",
    labels: str = "",
    components: str = "",
    related_context: str = "",
) -> str:
    """Generate a Jira ticket draft with description, scope, and exit criteria.
    scope, exit_criteria, labels, components are comma-separated strings."""
    return json.dumps(_jira.create_ticket(
        title, description,
        scope=[s.strip() for s in scope.split(",") if s.strip()] if scope else None,
        exit_criteria=[s.strip() for s in exit_criteria.split(",") if s.strip()] if exit_criteria else None,
        ticket_type=ticket_type, priority=priority,
        labels=[s.strip() for s in labels.split(",") if s.strip()] if labels else None,
        components=[s.strip() for s in components.split(",") if s.strip()] if components else None,
        related_context=related_context,
    ), indent=2)


@mcp.tool()
def jira_format_comment(
    comment: str,
    status_update: str = "",
    blockers: str = "",
    next_steps: str = "",
    mentions: str = "",
) -> str:
    """Format a Jira issue comment in wiki markup. blockers, next_steps, mentions are comma-separated."""
    return json.dumps(_jira.format_comment(
        comment, status_update,
        blockers=[s.strip() for s in blockers.split(",") if s.strip()] if blockers else None,
        next_steps=[s.strip() for s in next_steps.split(",") if s.strip()] if next_steps else None,
        mentions=[s.strip() for s in mentions.split(",") if s.strip()] if mentions else None,
    ), indent=2)


@mcp.tool()
def jira_list_drafts() -> str:
    """List saved Jira ticket drafts."""
    return json.dumps(_jira.list_drafts(), indent=2)


@mcp.tool()
def jira_read_draft(filename: str) -> str:
    """Read a saved Jira ticket draft by filename."""
    return _jira.read_draft(filename)


# ════════════════════════════════════════════════════════════════════
#  MEETING NOTES
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_one_on_one(
    person: str,
    topics: str = "",
    action_items: str = "",
    notes: str = "",
    date: str = "",
) -> str:
    """Create a 1:1 meeting note. topics and action_items are comma-separated."""
    return json.dumps(_meetings.create_one_on_one(
        person,
        topics=[s.strip() for s in topics.split(",") if s.strip()] if topics else None,
        action_items=[s.strip() for s in action_items.split(",") if s.strip()] if action_items else None,
        notes=notes, date=date,
    ), indent=2)


@mcp.tool()
def create_meeting_note(
    title: str,
    attendees: str = "",
    topics: str = "",
    decisions: str = "",
    action_items: str = "",
    notes: str = "",
    date: str = "",
) -> str:
    """Create a general meeting note. List args are comma-separated strings."""
    return json.dumps(_meetings.create_meeting_note(
        title,
        attendees=[s.strip() for s in attendees.split(",") if s.strip()] if attendees else None,
        topics=[s.strip() for s in topics.split(",") if s.strip()] if topics else None,
        decisions=[s.strip() for s in decisions.split(",") if s.strip()] if decisions else None,
        action_items=[s.strip() for s in action_items.split(",") if s.strip()] if action_items else None,
        notes=notes, date=date,
    ), indent=2)


@mcp.tool()
def add_to_meeting(filename: str, section: str, content: str) -> str:
    """Append content to a section of an existing meeting note."""
    return json.dumps(_meetings.add_to_meeting(filename, section, content), indent=2)


@mcp.tool()
def read_meeting(filename: str) -> str:
    """Read a meeting note by filename (partial match works)."""
    return json.dumps(_meetings.read_meeting(filename), indent=2)


@mcp.tool()
def list_meetings(days_back: int = 30, person: str = "") -> str:
    """List recent meeting notes. Optionally filter by person name."""
    return json.dumps(_meetings.list_meetings(days_back, person), indent=2)


@mcp.tool()
def search_meetings(query: str, days_back: int = 90) -> str:
    """Search across all meeting notes."""
    return json.dumps(_meetings.search_meetings(query, days_back), indent=2)


@mcp.tool()
def get_open_action_items(days_back: int = 30) -> str:
    """Find all unchecked action items across recent meeting notes."""
    return json.dumps(_meetings.get_open_action_items(days_back), indent=2)


# ════════════════════════════════════════════════════════════════════
#  NEWS TOOLS
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def news_categories() -> str:
    """List available news categories."""
    return json.dumps(_news.get_available_categories())


@mcp.tool()
def news_report(categories: str = "tech,cybersecurity", max_per_source: int = 5) -> str:
    """Fetch news and compile a markdown report. Categories are comma-separated."""
    cat_list = [c.strip() for c in categories.split(",") if c.strip()]
    return _news.compile_report(cat_list, max_per_source)


# ════════════════════════════════════════════════════════════════════
#  WEATHER TOOLS
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def current_weather() -> str:
    """Get current weather conditions (Montreal by default)."""
    return json.dumps(_weather.current_weather(), indent=2)


@mcp.tool()
def weather_forecast(days: int = 7) -> str:
    """Get daily weather forecast. days=1 for today, up to 16."""
    return json.dumps(_weather.daily_forecast(days), indent=2)


@mcp.tool()
def weather_report() -> str:
    """Generate a formatted markdown weather report for the week."""
    return _weather.weekly_report()


@mcp.tool()
def weather_today() -> str:
    """Generate a formatted markdown weather report for today."""
    return _weather.daily_report()


# ════════════════════════════════════════════════════════════════════
#  WORK JOURNAL
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def journal_log(entry: str, tags: str = "", date: str = "") -> str:
    """Log a timestamped work journal entry. tags are comma-separated."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return json.dumps(_journal.log_entry(entry, tag_list, date), indent=2)


@mcp.tool()
def journal_read(date: str = "") -> str:
    """Read today's (or a specific date's) journal entries."""
    return json.dumps(_journal.read_journal(date), indent=2)


@mcp.tool()
def journal_range(days_back: int = 7) -> str:
    """Read journal entries for the last N days."""
    return json.dumps(_journal.read_journal_range(days_back), indent=2)


@mcp.tool()
def journal_search(query: str, days_back: int = 90) -> str:
    """Search journal entries across multiple days."""
    return json.dumps(_journal.search_journal(query, days_back), indent=2)


@mcp.tool()
def journal_weekly_summary(weeks_back: int = 0) -> str:
    """Get a summary of journal entries for a given week."""
    return json.dumps(_journal.weekly_summary(weeks_back), indent=2)


# ════════════════════════════════════════════════════════════════════
#  BLOG TOOLS (Jekyll)
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def blog_create_draft(
    title: str,
    tags: str = "",
    categories: str = "",
    excerpt: str = "",
    body: str = "",
    series: str = "",
    part: int = 0,
) -> str:
    """Create a new Jekyll blog draft."""
    return json.dumps(_blog.create_draft(
        title,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
        categories=[c.strip() for c in categories.split(",") if c.strip()] if categories else None,
        excerpt=excerpt, body=body, series=series,
        part=part if part else None,
    ), indent=2)


@mcp.tool()
def blog_create_post(
    title: str,
    tags: str = "",
    categories: str = "",
    excerpt: str = "",
    body: str = "",
    series: str = "",
    part: int = 0,
    date: str = "",
) -> str:
    """Create a dated Jekyll blog post (ready to publish)."""
    return json.dumps(_blog.create_post(
        title,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
        categories=[c.strip() for c in categories.split(",") if c.strip()] if categories else None,
        excerpt=excerpt, body=body, series=series,
        part=part if part else None,
        date=date if date else None,
    ), indent=2)


@mcp.tool()
def blog_publish_draft(draft_filename: str, date: str = "") -> str:
    """Move a draft to _posts with today's date (or a specified date)."""
    return json.dumps(_blog.publish_draft(draft_filename, date if date else None), indent=2)


@mcp.tool()
def blog_list_drafts() -> str:
    """List all blog drafts."""
    return json.dumps(_blog.list_drafts(), indent=2)


@mcp.tool()
def blog_list_recent_posts(count: int = 10) -> str:
    """List the most recent published blog posts."""
    return json.dumps(_blog.list_recent_posts(count), indent=2)


@mcp.tool()
def blog_common_tags() -> str:
    """Return commonly used blog tags."""
    return json.dumps(_blog.get_common_tags())


@mcp.tool()
def blog_common_categories() -> str:
    """Return commonly used blog categories."""
    return json.dumps(_blog.get_common_categories())


# ── Jekyll Expert Tools ──────────────────────────────────────────────

@mcp.tool()
def jekyll_read_post(filename: str) -> str:
    """Read a blog post with parsed front matter and body."""
    return json.dumps(_jekyll.read_post(filename), indent=2)


@mcp.tool()
def jekyll_read_config() -> str:
    """Read the Jekyll _config.yml file."""
    return _jekyll.read_config()


@mcp.tool()
def jekyll_site_structure() -> str:
    """Get an overview of the Jekyll site structure."""
    return json.dumps(_jekyll.site_structure(), indent=2)


@mcp.tool()
def jekyll_analyze_post(filename: str) -> str:
    """Analyze a post for common Jekyll issues (missing fields, broken images, etc.)."""
    return json.dumps(_jekyll.analyze_post(filename), indent=2)


@mcp.tool()
def jekyll_update_front_matter(filename: str, field: str, value: str) -> str:
    """Update a single front matter field in a post."""
    return json.dumps(_jekyll.update_front_matter(filename, {field: value}), indent=2)


# ════════════════════════════════════════════════════════════════════
#  BLOG WRITER — post scaffolding tools
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def blog_suggest_titles(topic: str, description: str = "") -> str:
    """Suggest 5 blog post titles in the 'ProjectName: Subtitle' format.

    Args:
        topic: The project or topic name (e.g. "RaceFlow", "my Discord bot").
        description: Optional one-line description of what it does or the angle.
    """
    return json.dumps(_blog_writer.suggest_titles(topic, description), indent=2)


@mcp.tool()
def blog_scaffold_post(
    title: str,
    topic_summary: str,
    post_type: str = "project",
    tags: str = "",
    series: str = "",
    part: int = 0,
) -> str:
    """Create a fully scaffolded _draft with the blog's section structure.

    Saves a new draft file with Foreword, Introduction, numbered Parts,
    'What I'd Do Differently', Conclusion, and Resources — all pre-filled
    with [FILL: ...] placeholders so you're never staring at a blank page.

    Args:
        title: Full post title (e.g. "TracksMartin: Hits on Demand").
        topic_summary: 1-3 sentence description of what the post covers.
        post_type: One of 'project' (default), 'tutorial', 'series_part', 'thoughts'.
        tags: Comma-separated list of tags (e.g. "python,cli,music").
        series: Series name if this is part of a series (e.g. "RaceFlow").
        part: Part number if this is a series post (e.g. 1). Use 0 if not a series.
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return json.dumps(
        _blog_writer.scaffold_post(
            title=title,
            topic_summary=topic_summary,
            post_type=post_type,
            tags=tag_list,
            series=series,
            part=part or None,
        ),
        indent=2,
    )


@mcp.tool()
def blog_draft_foreword(project_name: str, context: str, tone_notes: str = "") -> str:
    """Generate a foreword template for a new blog post.

    The foreword is always the hardest part to start. This returns a
    fill-in-the-blanks skeleton:
    personal hook → honest admission → external trigger → natural transition to tech.

    Args:
        project_name: Name of the project or thing the post is about.
        context: 2-4 sentences explaining what it is and why you built it.
        tone_notes: Optional hints about tone (e.g. 'friend suggested it',
                    'frustrated with existing tools', 'obvious in retrospect').
    """
    return _blog_writer.draft_foreword(project_name, context, tone_notes)


# ════════════════════════════════════════════════════════════════════
#  CODE DOCUMENTATION
# ════════════════════════════════════════════════════════════════════

@mcp.tool()
def codedoc_scan(path: str) -> str:
    """Scan a codebase and return a structural overview: languages, file counts, key files, directory layout."""
    return json.dumps(_codedoc.scan_codebase(path), indent=2)


@mcp.tool()
def codedoc_module(file_path: str) -> str:
    """Document a single source file. Extracts classes, functions, docstrings, params, and type hints."""
    return json.dumps(_codedoc.document_module(file_path), indent=2)


@mcp.tool()
def codedoc_generate(path: str, title: str = "", include_private: bool = False) -> str:
    """Generate comprehensive markdown documentation for an entire codebase. Returns a full markdown string."""
    return _codedoc.generate_docs(path, title, include_private)


@mcp.tool()
def codedoc_readme(path: str, project_name: str = "", description: str = "") -> str:
    """Generate a README.md skeleton from codebase analysis. Detects install commands, prereqs, and structure."""
    return _codedoc.generate_readme(path, project_name, description)


@mcp.tool()
def codedoc_api(path: str) -> str:
    """Extract and document API endpoints from a Python web project (Flask, FastAPI, Django)."""
    return _codedoc.document_api(path)


# ════════════════════════════════════════════════════════════════════
#  SSE TRANSPORT — SECURITY
# ════════════════════════════════════════════════════════════════════

SSE_HOST = "127.0.0.1"   # NEVER bind to 0.0.0.0 — this server has full account access
SSE_PORT = 8808
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "sse_token.txt")


def _get_or_create_token() -> str:
    """Load existing bearer token or generate a new one."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
            if token:
                return token
    token = secrets.token_urlsafe(48)
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    return token


class _BearerAuthMiddleware:
    """ASGI middleware requiring a valid Bearer token on every HTTP request."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    OPEN_PATHS = {"/health"}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path not in self.OPEN_PATHS:
                headers = dict(scope.get("headers", []))
                auth = headers.get(b"authorization", b"").decode()
                if not auth.startswith("Bearer ") or not secrets.compare_digest(
                    auth[7:], self.token
                ):
                    from starlette.responses import Response

                    resp = Response("Unauthorized", status_code=401, media_type="text/plain")
                    await resp(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# ════════════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workstation Agent MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse"], default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument("--host", default=SSE_HOST, help="SSE bind address")
    parser.add_argument("--port", type=int, default=SSE_PORT, help="SSE port")
    args = parser.parse_args()

    if args.transport == "sse":
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        from mcp.server.sse import SseServerTransport

        token = _get_or_create_token()
        sse_transport = SseServerTransport("/messages/")
        mcp_server = mcp._mcp_server

        async def handle_sse(request):
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                init_opts = mcp_server.create_initialization_options()
                await mcp_server.run(read_stream, write_stream, init_opts)

        async def health(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"status": "ok", "server": "workstation-agent"})

        app = Starlette(
            routes=[
                Route("/health", endpoint=health),
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse_transport.handle_post_message),
            ]
        )
        secured_app = _BearerAuthMiddleware(app, token)

        logger.info("Starting Workstation Agent MCP server (SSE)...")
        logger.info("  Endpoint: http://%s:%d/sse", args.host, args.port)
        logger.info("  Health:   http://%s:%d/health", args.host, args.port)
        logger.info("  Token:    %s", token)

        uvicorn.run(secured_app, host=args.host, port=args.port, log_level="info")
    else:
        logger.info("Starting Workstation Agent MCP server (stdio)...")
        mcp.run(transport="stdio")
