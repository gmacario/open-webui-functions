"""
title: A filter function to trace LLM calls using Langfuse
author: Gianpaolo Macario (gmacario)
date: 2026-04-24
author_url: https://github.com/gmacario/openwebui_langfuse
funding_url: https://github.com/gmacario/openwebui_langfuse
version: 0.1
license: MIT
description: A filter function that uses Langfuse v4.
required_open_webui_version: 0.9.1
requirements: langfuse>=4.0.0
Other notes: Based upon https://github.com/YetheSamartaka/open-webui-functions
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any

from langfuse import Langfuse
from pydantic import BaseModel, Field
from typing import Optional


class Filter:
    class Valves(BaseModel):
        # priority: int = Field(
        #     default=0, description="Priority level for the filter operations."
        # )
        # max_turns: int = Field(
        #     default=8, description="Maximum allowable conversation turns for a user."
        # )
        # pass
        secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "your-secret-key-here")
        public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "your-public-key-here")
        host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        insert_tags: bool = True
        disable_debug_bodies: bool = Field(
            default=False,
            title="Disable debug bodies",
        )
        use_model_name_instead_of_id_for_generation: bool = (
            os.getenv("USE_MODEL_NAME", "false").lower() == "true"
        )
        debug: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # class UserValves(BaseModel):
    #     max_turns: int = Field(
    #         default=4, description="Maximum allowable conversation turns for a user."
    #     )
    #     pass

    def __init__(self):
        # Indicates custom file handling logic. This flag helps disengage default routines in favor of custom
        # implementations, informing the WebUI to defer file-related operations to designated methods within this class.
        # Alternatively, you can remove the files directly from the body in from the inlet hook
        # self.file_handler = True

        self.type = "filter"
        self.name = "Langfuse Filter"

        # Initialize 'valves' with specific configurations. Using 'Valves' instance helps encapsulate settings,
        # which ensures settings are managed cohesively and not confused with operational flags like 'file_handler'.
        self.valves = self.Valves()

        self.langfuse: Langfuse | None = None
        self.chat_trace_ids: dict[str, str] = {}
        self.chat_tags: dict[str, set[str]] = {}
        self.suppressed_logs: set[str] = set()
        self.session_to_chat_id: dict[str, str] = {}
        self._set_langfuse()

    def _drop_keys_recursive(self, obj: Any, drop: set[str]) -> Any:
        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                if isinstance(k, str) and k in drop:
                    continue
                out[k] = self._drop_keys_recursive(v, drop)
            return out
        if isinstance(obj, list):
            return [self._drop_keys_recursive(v, drop) for v in obj]
        return obj

    def _scrub_for_debug(self, obj: Any) -> Any:
        return self._drop_keys_recursive(
            obj, {"knowledge", "profile_image_url", "files"}
        )

    def _debug_prefix(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return f"{ts} | GM_DEBUG | "

    def log(self, message: str, suppress_repeats: bool = False) -> None:
        # if not self.valves.debug:
        #    return
        #
        # scrubbed = self._scrub_debug_message(message)
        # if scrubbed is None:
        #     return
        #
        # if suppress_repeats:
        #    if scrubbed in self.suppressed_logs:
        #        return
        #    self.suppressed_logs.add(scrubbed)
        #
        # print(f"{self._debug_prefix()}{scrubbed}")
        # print(f"GM_INFO3 | {message}")
        print(f"{self._debug_prefix()}{message}")

    async def on_valves_updated(self) -> None:
        self.log("Valves updated, resetting Langfuse client.")
        self._set_langfuse()

    def _sanitize_debug_content(self, obj: Any) -> Any:
        if self.valves.debug:
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitize_debug_content(v) for k, v in obj.items()}
        if isinstance(obj, list):
            sanitized_list = [self._sanitize_debug_content(v) for v in obj]
            return [v for v in sanitized_list if v not in ("", None, [], {})]
        if isinstance(obj, str):
            return self._strip_debug_from_string(obj)
        return obj

    def _build_trace_metadata(
        self, metadata: dict[str, Any], user_email: str | None, chat_id: str
    ) -> dict[str, Any]:
        base_metadata: dict[str, Any] = {
            **metadata,
            "user_id": user_email,
            "session_id": chat_id,
            "interface": "open-webui",
        }
        return self._sanitize_debug_content(base_metadata)

    def _build_safe_input(
        self, body: dict[str, Any], trace_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        safe_body: dict[str, Any] = {
            "model": body.get("model"),
            "messages": body.get("messages"),
        }
        safe_body["metadata"] = self._sanitize_debug_content(trace_metadata)
        return safe_body

    def _set_langfuse(self) -> None:
        self.log("_set_langfuse")
        try:
            self.log(f"Initializing Langfuse with host: {self.valves.host}")
            self.log(
                "Secret key set: "
                + (
                    "Yes"
                    if self.valves.secret_key
                    and self.valves.secret_key != "your-secret-key-here"
                    else "No"
                )
            )
            self.log(
                "Public key set: "
                + (
                    "Yes"
                    if self.valves.public_key
                    and self.valves.public_key != "your-public-key-here"
                    else "No"
                )
            )
            self.langfuse = Langfuse(
                secret_key=self.valves.secret_key,
                public_key=self.valves.public_key,
                host=self._normalize_host(self.valves.host),
                debug=self.valves.debug,
            )
            try:
                self.langfuse.auth_check()
                self.log(
                    f"Langfuse client initialized and authenticated successfully. Connected to host: {self.valves.host}"
                )
            except Exception as e:
                self.log(f"Auth check failed (non-critical, skipping): {e}")
        except Exception as auth_error:
            msg = str(auth_error)
            if (
                "401" in msg
                or "unauthorized" in msg.lower()
                or "credentials" in msg.lower()
            ):
                self.log(f"Langfuse credentials incorrect: {auth_error}")
                self.langfuse = None
            else:
                self.log(f"Langfuse initialization error: {auth_error}")
                self.langfuse = None

    def _normalize_host(self, raw: str) -> str:
        v = (raw or "").strip().rstrip("/")
        if not v:
            return "https://cloud.langfuse.com"
        if v.startswith("http://") or v.startswith("https://"):
            return v
        return f"https://{v}"

    def _update_persistent_tags_for_chat(
        self, chat_id: str | None, tags: list[str]
    ) -> None:
        if not chat_id:
            return
        if chat_id not in self.chat_tags:
            self.chat_tags[chat_id] = set()
        for t in tags:
            if isinstance(t, str):
                self.chat_tags[chat_id].add(t)
        self.log(
            f"Updated persistent tags for chat_id {chat_id}: {sorted(self.chat_tags[chat_id])}"
        )

    def _get_or_create_trace_id(self, chat_id: str) -> str:
        cached = self.chat_trace_ids.get(chat_id)
        if cached:
            return cached
        trace_id = Langfuse.create_trace_id(seed=chat_id)
        self.chat_trace_ids[chat_id] = trace_id
        self.log(f"Deterministic trace_id for chat_id {chat_id}: {trace_id}")
        return trace_id

    def _extract_session_id(self, body: dict[str, Any]) -> str | None:
        metadata = body.get("metadata", {}) or {}
        raw_session_id = metadata.get("session_id") or body.get("session_id")
        if isinstance(raw_session_id, str) and raw_session_id:
            return raw_session_id
        return None

    def _extract_chat_id(self, body: dict[str, Any]) -> str:
        metadata = body.get("metadata", {}) or {}
        raw_chat_id = body.get("chat_id") or metadata.get("chat_id")
        session_id = self._extract_session_id(body)

        if isinstance(raw_chat_id, str) and raw_chat_id.startswith("task-"):
            task_body = metadata.get("task_body")
            if isinstance(task_body, dict):
                tb_chat_id = task_body.get("chat_id")
                if (
                    isinstance(tb_chat_id, str)
                    and tb_chat_id
                    and not tb_chat_id.startswith("task-")
                ):
                    raw_chat_id = tb_chat_id

            if session_id:
                mapped = self.session_to_chat_id.get(session_id)
                if mapped:
                    return mapped

        chat_id: str | None = (
            raw_chat_id if isinstance(raw_chat_id, str) and raw_chat_id else None
        )

        if chat_id == "local":
            session_id_for_local = metadata.get("session_id") or body.get("session_id")
            session_str = (
                session_id_for_local
                if isinstance(session_id_for_local, str) and session_id_for_local
                else str(uuid.uuid4())
            )
            chat_id = f"temporary-session-{session_str}"

        if not chat_id:
            session_id_for_missing = metadata.get("session_id") or body.get(
                "session_id"
            )
            if isinstance(session_id_for_missing, str) and session_id_for_missing:
                chat_id = f"temporary-session-{session_id_for_missing}"
            else:
                chat_id = str(uuid.uuid4())

        if session_id and not chat_id.startswith("task-"):
            self.session_to_chat_id[session_id] = chat_id

        return chat_id

    async def inlet(
        self, body: dict[str, Any], __event_emitter__, __user__: Optional[dict] = None
    ) -> dict[str, Any]:
        # Modify the request body or validate it before processing by the chat completion API.
        # This function is the pre-processor for the API where various checks on the input can be performed.
        # It can also modify the request before sending it to the API.
        #
        # print(f"GM_DEBUG - inlet:{__name__}")
        # print(f"GM_DEBUG - inlet:body:{body}")
        # print(f"GM_INFO - inlet:user:{__user__}")
        #
        # self.log("inlet: Hello, world!")
        #
        # if __user__.get("role", "admin") in ["user", "admin"]:
        #    messages = body.get("messages", [])
        #
        #    max_turns = min(__user__["valves"].max_turns, self.valves.max_turns)
        #    if len(messages) > max_turns:
        #        raise Exception(
        #            f"Conversation turn limit exceeded. Max turns: {max_turns}"
        #        )
        #
        self.log("Langfuse Filter INLET called")
        self._set_langfuse()
        if not self.langfuse:
            self.log("[WARNING] Langfuse client not initialized - Skipped")
            return body

        self.log(f"inlet: self.valves.secret_key={self.valves.secret_key}")  # DEBUG
        self.log(f"inlet: self.valves.public_key={self.valves.public_key}")  # DEBUG
        self.log(f"inlet: self.valves.host={self.valves.host}")  # DEBUG

        user_scrubbed = (
            self._scrub_for_debug(__user__) if __user__ is not None else None
        )
        if self.valves.disable_debug_bodies:
            self.log(
                f"Inlet function called with body summary: {self._debug_body_summary(body)} and user: {user_scrubbed}"
            )
        else:
            self.log(
                f"Inlet function called with body: {self._scrub_for_debug(body)} and user: {user_scrubbed}"
            )

        required_keys = ["model", "messages"]
        missing_keys = [key for key in required_keys if key not in body]
        if missing_keys:
            error_message = (
                f"Error: Missing keys in the request body: {', '.join(missing_keys)}"
            )
            self.log(error_message)
            raise ValueError(error_message)

        metadata = body.get("metadata", {}) or {}
        chat_id = self._extract_chat_id(body)

        user_email = __user__.get("email") if __user__ else None
        tags_list: list[str] = []

        self._update_persistent_tags_for_chat(chat_id, tags_list)
        _ = self._get_or_create_trace_id(chat_id)

        trace_metadata = self._build_trace_metadata(dict(metadata), user_email, chat_id)
        _ = self._build_safe_input(body, trace_metadata)

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify or analyze the response body after processing by the API.
        # This function is the post-processor for the API, which can be used to modify the response
        # or perform additional checks and analytics.
        #
        self.log(f"outlet:{__name__}")
        # print(f"GM_DEBUG - outlet:body:{body}")
        # print(f"GM_INFO - outlet:user:{__user__}")
        #
        self.log("outlet: END")
        # print("GM_INFO: outlet: END")
        #
        return body


# EOF
