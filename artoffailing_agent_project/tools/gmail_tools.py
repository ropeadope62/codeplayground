"""
Gmail tools — read, search, and send via the Gmail API.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from .google_auth import get_google_credentials


class GmailTools:
    def __init__(self):
        creds = get_google_credentials()
        self.service = build("gmail", "v1", credentials=creds)
        self.user_id = "me"

    def list_messages(self, query: str = "", max_results: int = 10, label: str = "INBOX") -> dict:
        """List messages with pagination support.

        Returns a dict with 'messages' (list) and 'next_page_token' (str or None).
        The Gmail API returns up to 500 message IDs per page, but we fetch
        metadata individually, so we cap at max_results for sanity.
        """
        max_results = min(max_results, 500)

        summaries = []
        page_token = None
        remaining = max_results

        while remaining > 0:
            # Gmail list API maxResults caps at 500
            page_size = min(remaining, 500)
            kwargs: dict = {
                "userId": self.user_id,
                "q": query,
                "maxResults": page_size,
            }
            if label:
                kwargs["labelIds"] = [label]
            if page_token:
                kwargs["pageToken"] = page_token

            results = self.service.users().messages().list(**kwargs).execute()

            for msg_ref in results.get("messages", []):
                msg = self.service.users().messages().get(
                    userId=self.user_id, id=msg_ref["id"], format="metadata",
                    metadataHeaders=["Subject", "From", "Date", "To"],
                ).execute()
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                summaries.append({
                    "id": msg["id"],
                    "thread_id": msg["threadId"],
                    "subject": headers.get("Subject", "(no subject)"),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                    "is_unread": "UNREAD" in msg.get("labelIds", []),
                })
                remaining -= 1
                if remaining <= 0:
                    break

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return {
            "messages": summaries,
            "next_page_token": page_token,
            "count": len(summaries),
        }

    def read_message(self, message_id: str) -> dict:
        msg = self.service.users().messages().get(
            userId=self.user_id, id=message_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        body = self._extract_body(msg.get("payload", {}))
        return {
            "id": msg["id"], "thread_id": msg["threadId"],
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""), "to": headers.get("To", ""),
            "date": headers.get("Date", ""), "body": body,
            "labels": msg.get("labelIds", []),
        }

    def get_unread_count(self) -> int:
        results = self.service.users().messages().list(
            userId=self.user_id, q="is:unread", labelIds=["INBOX"]
        ).execute()
        return results.get("resultSizeEstimate", 0)

    def send_email(self, to: str, subject: str, body: str) -> dict:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = self.service.users().messages().send(
            userId=self.user_id, body={"raw": encoded}
        ).execute()
        return {"action": "sent", "id": result["id"], "thread_id": result["threadId"], "to": to, "subject": subject}

    def create_draft(self, to: str, subject: str, body: str) -> dict:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = self.service.users().drafts().create(
            userId=self.user_id, body={"message": {"raw": encoded}}
        ).execute()
        return {"action": "draft_created", "draft_id": result["id"], "to": to, "subject": subject}

    def batch_modify_labels(
        self,
        message_ids: list[str],
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict:
        """Add or remove labels from a batch of messages."""
        body: dict = {"ids": message_ids}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        self.service.users().messages().batchModify(
            userId=self.user_id, body=body
        ).execute()
        return {"action": "batch_modified", "count": len(message_ids), "added": add_labels, "removed": remove_labels}

    def modify_message_labels(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict:
        """Add or remove labels from a single message."""
        body: dict = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        result = self.service.users().messages().modify(
            userId=self.user_id, id=message_id, body=body
        ).execute()
        return {"action": "modified", "id": result["id"], "labels": result.get("labelIds", [])}

    def bulk_organize(
        self,
        operations: list[dict],
    ) -> dict:
        """Apply multiple label operations in one call.

        Each operation is a dict with:
          - message_ids: list of message IDs
          - add_labels: list of label IDs to add (optional)
          - remove_labels: list of label IDs to remove (optional)

        Example:
          [
            {"message_ids": ["id1", "id2"], "add_labels": ["TRASH"], "remove_labels": ["INBOX", "UNREAD"]},
            {"message_ids": ["id3"], "add_labels": ["CATEGORY_UPDATES"], "remove_labels": ["UNREAD"]},
          ]
        """
        results = []
        for op in operations:
            ids = op.get("message_ids", [])
            add = op.get("add_labels") or None
            remove = op.get("remove_labels") or None
            if not ids:
                continue
            if len(ids) == 1:
                # Single message — use modify
                body: dict = {}
                if add:
                    body["addLabelIds"] = add
                if remove:
                    body["removeLabelIds"] = remove
                self.service.users().messages().modify(
                    userId=self.user_id, id=ids[0], body=body
                ).execute()
                results.append({
                    "action": "modified",
                    "count": 1,
                    "message_ids": ids,
                    "added": add,
                    "removed": remove,
                })
            else:
                # Multiple messages — use batchModify
                body = {"ids": ids}
                if add:
                    body["addLabelIds"] = add
                if remove:
                    body["removeLabelIds"] = remove
                self.service.users().messages().batchModify(
                    userId=self.user_id, body=body
                ).execute()
                results.append({
                    "action": "batch_modified",
                    "count": len(ids),
                    "message_ids": ids,
                    "added": add,
                    "removed": remove,
                })
        return {"operations_completed": len(results), "details": results}

    def list_labels(self) -> list[dict]:
        """List all Gmail labels for the user."""
        result = self.service.users().labels().list(userId=self.user_id).execute()
        return [
            {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "")}
            for lbl in result.get("labels", [])
        ]

    def create_label(self, name: str) -> dict:
        """Create a new Gmail label."""
        body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        result = self.service.users().labels().create(userId=self.user_id, body=body).execute()
        return {"action": "created", "id": result["id"], "name": result["name"]}

    def delete_label(self, label_id: str) -> dict:
        """Delete a user-created Gmail label by ID."""
        self.service.users().labels().delete(userId=self.user_id, id=label_id).execute()
        return {"action": "deleted", "id": label_id}

    def rename_label(self, label_id: str, new_name: str) -> dict:
        """Rename an existing Gmail label."""
        result = self.service.users().labels().patch(
            userId=self.user_id, id=label_id, body={"name": new_name}
        ).execute()
        return {"action": "renamed", "id": result["id"], "name": result["name"]}

    def _extract_body(self, payload: dict) -> str:
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            if part.get("parts"):
                result = self._extract_body(part)
                if result:
                    return result
        return "(no plain text body found)"
