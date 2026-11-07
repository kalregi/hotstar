"""Password-gated host recovery and closing of shared games."""

import secrets
from datetime import datetime, timezone


ACTIVE_STATUSES = ("playing", "final_round")


class HostGames:
    def __init__(self, database, expected_password):
        self.database = database
        self.expected_password = expected_password

    def authorized(self, password):
        return bool(self.expected_password) and secrets.compare_digest(
            password.encode("utf-8"), self.expected_password.encode("utf-8")
        )

    def require_password(self, password):
        if not self.authorized(password):
            raise PermissionError("Hibás host jelszó.")

    def list_active(self, password):
        self.require_password(password)
        games = []
        while True:
            batch = (
                self.database.table("games")
                .select("game_code,game_status,number_of_teams,teams,host_id,host_last_seen")
                .in_("game_status", ACTIVE_STATUSES)
                .order("host_last_seen", desc=True)
                .order("game_code")
                .range(len(games), len(games) + 499)
                .execute().data
            ) or []
            games.extend(batch)
            if len(batch) < 500:
                return games

    def resume(self, password, game_code, device_id):
        self.require_password(password)
        rows = (
            self.database.table("games")
            .update({"host_id": device_id,
                     "host_last_seen": datetime.now(timezone.utc).isoformat()})
            .eq("game_code", game_code)
            .in_("game_status", ACTIVE_STATUSES)
            .execute().data
        )
        if not rows:
            raise ValueError("Ez a játék már nem folyamatban lévő játék. Frissítsd a listát.")
        return rows[0]

    def close(self, password, game_code):
        self.require_password(password)
        rows = (
            self.database.table("games")
            .update({"game_status": "closed", "host_id": None, "host_last_seen": None})
            .eq("game_code", game_code)
            .in_("game_status", ACTIVE_STATUSES)
            .execute().data
        )
        if not rows:
            raise ValueError("Ez a játék már lezárult vagy nem található. Frissítsd a listát.")
