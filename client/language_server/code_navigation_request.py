# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
This module contains the definition of code navigation requests and an API to convert a given LSP request
to a corresponding code navigation request. Also contains an API that sends a given request to the code navigation
server and gets a response.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from .. import dataclasses_json_extensions as json_mixins

from . import daemon_connection, protocol as lsp


@dataclasses.dataclass(frozen=True)
class HoverRequest:
    path: Path
    overlay_id: Optional[str]
    position: lsp.PyrePosition

    def to_json(self) -> List[object]:
        return [
            "Hover",
            {
                "module": ["OfPath", f"{self.path}"],
                "overlay_id": self.overlay_id,
                "position": {
                    "line": self.position.line,
                    "column": self.position.character,
                },
            },
        ]


@dataclasses.dataclass(frozen=True)
class LocationOfDefinitionRequest:
    path: Path
    overlay_id: Optional[str]
    position: lsp.PyrePosition

    def to_json(self) -> List[object]:
        return [
            "LocationOfDefinition",
            {
                "module": ["OfPath", f"{self.path}"],
                "overlay_id": self.overlay_id,
                "position": {
                    "line": self.position.line,
                    "column": self.position.character,
                },
            },
        ]


@dataclasses.dataclass(frozen=True)
class ErrorResponse:
    message: str


@dataclasses.dataclass(frozen=True)
class HoverContent(json_mixins.CamlCaseAndExcludeJsonMixin):
    value: Optional[str]
    docstring: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class HoverResponse(json_mixins.CamlCaseAndExcludeJsonMixin):
    contents: List[HoverContent]


@dataclasses.dataclass(frozen=True)
class CodeNavigationPosition(json_mixins.CamlCaseAndExcludeJsonMixin):
    """LSP uses 0-indexing for lines whereas Pyre uses 1-indexing."""

    line: int
    column: int

    def to_lsp_position(self) -> lsp.LspPosition:
        return lsp.LspPosition(self.line - 1, self.column)


@dataclasses.dataclass(frozen=True)
class CodeNavigationRange(json_mixins.CamlCaseAndExcludeJsonMixin):
    start: CodeNavigationPosition
    stop: CodeNavigationPosition

    def to_lsp_range(self) -> lsp.LspRange:
        return lsp.LspRange(
            start=self.start.to_lsp_position(),
            end=self.stop.to_lsp_position(),
        )


@dataclasses.dataclass(frozen=True)
class DefinitionResponse:
    path: str
    range: CodeNavigationRange

    def to_lsp_definition_response(self) -> lsp.LspLocation:
        return lsp.LspLocation(uri=self.path, range=self.range.to_lsp_range())


@dataclasses.dataclass(frozen=True)
class LocationOfDefinitionResponse(json_mixins.CamlCaseAndExcludeJsonMixin):
    definitions: List[DefinitionResponse]


@dataclasses.dataclass(frozen=True)
class LocalUpdate:
    path: Path
    content: str
    overlay_id: str

    def to_json(self) -> List[object]:
        return [
            "LocalUpdate",
            {
                "module": ["OfPath", f"{self.path}"],
                "content": self.content,
                "overlay_id": self.overlay_id,
            },
        ]


@dataclasses.dataclass(frozen=True)
class FileOpened:
    path: Path
    content: str
    overlay_id: str

    def to_json(self) -> List[object]:
        return [
            "FileOpened",
            {
                "path": f"{self.path}",
                "content": self.content,
                "overlay_id": self.overlay_id,
            },
        ]


@dataclasses.dataclass(frozen=True)
class FileClosed:
    path: Path
    overlay_id: str

    def to_json(self) -> List[object]:
        return [
            "FileClosed",
            {
                "path": f"{self.path}",
                "overlay_id": self.overlay_id,
            },
        ]


def invalid_response(response: str) -> ErrorResponse:
    return ErrorResponse(message=f"Invalid response {response} to hover request.")


ResponseKind = TypeVar("ResponseKind", bound=json_mixins.CamlCaseAndExcludeJsonMixin)


def parse_response(
    response: Dict[str, Any], response_type: Type[ResponseKind]
) -> ResponseKind | ErrorResponse:
    try:
        return response_type.cached_schema().load(response)
    except AssertionError as error:
        return ErrorResponse(
            message=f"Assertion error when parsing JSON into the response schema: {error}"
        )


def parse_raw_response(
    raw_response: str, expected_response_kind: str, response_type: Type[ResponseKind]
) -> ResponseKind | ErrorResponse:
    try:
        response = json.loads(raw_response)
        if (
            not isinstance(response, list)
            or len(response) != 2
            or response[0] != expected_response_kind
        ):
            return invalid_response(raw_response)
    except Exception as error:
        return ErrorResponse(message=f"Exception while parsing response: {error}")
    return parse_response(response[1], response_type)


async def async_handle_hover_request(
    socket_path: Path,
    hover_request: HoverRequest,
) -> Union[lsp.PyreHoverResponse, ErrorResponse]:
    raw_request = json.dumps(["Query", hover_request.to_json()])
    response = await daemon_connection.attempt_send_async_raw_request(
        socket_path, raw_request
    )
    if isinstance(response, daemon_connection.DaemonConnectionFailure):
        return ErrorResponse(message=response.error_message)
    response = parse_raw_response(
        response, expected_response_kind="Hover", response_type=HoverResponse
    )
    if isinstance(response, ErrorResponse):
        return response
    types = [content.value for content in response.contents]
    types = filter(lambda value: value is not None, types)
    return lsp.PyreHoverResponse(
        "\n".join(str(content.value) for content in response.contents),
        "\n".join(str(content.docstring) for content in response.contents),
    )


async def async_handle_definition_request(
    socket_path: Path,
    definition_request: LocationOfDefinitionRequest,
) -> Union[LocationOfDefinitionResponse, ErrorResponse]:
    raw_request = json.dumps(["Query", definition_request.to_json()])
    response = await daemon_connection.attempt_send_async_raw_request(
        socket_path, raw_request
    )
    if isinstance(response, daemon_connection.DaemonConnectionFailure):
        return ErrorResponse(message=response.error_message)
    return parse_raw_response(
        response,
        expected_response_kind="LocationOfDefinition",
        response_type=LocationOfDefinitionResponse,
    )


async def async_handle_local_update(
    socket_path: Path, local_update: LocalUpdate
) -> str | daemon_connection.DaemonConnectionFailure:
    raw_command = json.dumps(["Command", local_update.to_json()])
    response = await daemon_connection.attempt_send_async_raw_request(
        socket_path, raw_command
    )
    return response


async def async_handle_file_opened(
    socket_path: Path, file_opened: FileOpened
) -> str | daemon_connection.DaemonConnectionFailure:
    raw_command = json.dumps(["Command", file_opened.to_json()])
    response = await daemon_connection.attempt_send_async_raw_request(
        socket_path, raw_command
    )
    return response


async def async_handle_file_closed(
    socket_path: Path, file_closed: FileClosed
) -> str | daemon_connection.DaemonConnectionFailure:
    raw_command = json.dumps(["Command", file_closed.to_json()])
    response = await daemon_connection.attempt_send_async_raw_request(
        socket_path, raw_command
    )
    return response
