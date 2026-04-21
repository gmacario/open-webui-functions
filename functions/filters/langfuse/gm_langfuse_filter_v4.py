"""
title: A filter function to trace LLM calls using Langfuse
author: Gianpaolo Macario (gmacario)
date: 2026-04-21
author_url: https://github.com/gmacario/openwebui_langfuse
funding_url: https://github.com/gmacario/openwebui_langfuse
version: 0.1
license: MIT
description: A filter function that uses Langfuse v3 (v4?).
required_open_webui_version: 0.9.1
requirements: langfuse==3.14.5
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
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        max_turns: int = Field(
            default=8, description="Maximum allowable conversation turns for a user."
        )
        pass

    class UserValves(BaseModel):
        max_turns: int = Field(
            default=4, description="Maximum allowable conversation turns for a user."
        )
        pass

    def __init__(self):
        # Indicates custom file handling logic. This flag helps disengage default routines in favor of custom
        # implementations, informing the WebUI to defer file-related operations to designated methods within this class.
        # Alternatively, you can remove the files directly from the body in from the inlet hook
        # self.file_handler = True

        # Initialize 'valves' with specific configurations. Using 'Valves' instance helps encapsulate settings,
        # which ensures settings are managed cohesively and not confused with operational flags like 'file_handler'.
        self.valves = self.Valves()
        #
        # NOTE: CANNOT CALL log("__init__ complete") HERE!!!
        #
        pass

    def _debug_prefix(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return f"{ts} | GM_DEBUG_log    | "

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
        print(f"{self._debug_prefix()}{message}")

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify the request body or validate it before processing by the chat completion API.
        # This function is the pre-processor for the API where various checks on the input can be performed.
        # It can also modify the request before sending it to the API.
        #
        print(f"GM_INFO - inlet:{__name__}")
        # print(f"GM_DEBUG - inlet:body:{body}")
        # print(f"GM_INFO - inlet:user:{__user__}")

        # log("inlet: Hello, world!")

        # if __user__.get("role", "admin") in ["user", "admin"]:
        #    messages = body.get("messages", [])
        #
        #    max_turns = min(__user__["valves"].max_turns, self.valves.max_turns)
        #    if len(messages) > max_turns:
        #        raise Exception(
        #            f"Conversation turn limit exceeded. Max turns: {max_turns}"
        #        )
        #
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify or analyze the response body after processing by the API.
        # This function is the post-processor for the API, which can be used to modify the response
        # or perform additional checks and analytics.
        #
        print(f"GM_INFO - outlet:{__name__}")
        # print(f"GM_DEBUG - outlet:body:{body}")
        print(f"GM_INFO - outlet:user:{__user__}")
        #
        print("GM_INFO: outlet: END")
        #
        return body
