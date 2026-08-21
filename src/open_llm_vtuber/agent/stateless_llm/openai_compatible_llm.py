"""Description: This file contains the implementation of the `AsyncLLM` class.
This class is responsible for handling asynchronous interaction with OpenAI API compatible
endpoints for language generation.
"""

import re
from typing import AsyncIterator, List, Dict, Any
from openai import (
    AsyncStream,
    AsyncOpenAI,
    APIError,
    APIConnectionError,
    RateLimitError,
    NotGiven,
    NOT_GIVEN,
)
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from loguru import logger

from .stateless_llm_interface import StatelessLLMInterface
from ...mcpp.types import ToolCallObject


def _drop_leading_assistant_turns(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Drop assistant turns that appear before the conversation's first user turn.

    The character greets the user first, so a stored history normally begins with
    an assistant turn. Some chat templates refuse that shape outright — LM Studio's
    template for ``qwen/qwen3.5-9b`` fails the whole request with
    ``Error rendering prompt with jinja template: "No user query found in messages."``,
    which surfaces to the user as an unexplained "Error calling the chat endpoint".

    Verified against that model: ``[system, assistant, user]`` fails while
    ``[system, user, assistant, user]`` succeeds, so the trigger is specifically an
    assistant turn preceding the first user turn — not a mid-conversation system
    message and not OpenAI content-part arrays, both of which it accepts.

    Only the opening greeting is dropped; every turn from the first user message
    onward is preserved untouched, including assistant turns.
    """
    first_user = next(
        (i for i, m in enumerate(messages) if m.get("role") == "user"), None
    )
    if first_user is None:
        # No user turn at all: nothing to anchor on, so leave the list alone
        # rather than silently sending an empty conversation.
        return messages
    if first_user == 0:
        return messages
    # Keep anything else that leads (a system message belongs there); drop only
    # the assistant turns.
    head = [m for m in messages[:first_user] if m.get("role") != "assistant"]
    return [*head, *messages[first_user:]]


class AsyncLLM(StatelessLLMInterface):
    def __init__(
        self,
        model: str,
        base_url: str,
        llm_api_key: str = "z",
        organization_id: str = "z",
        project_id: str = "z",
        temperature: float = 1.0,
        extra_body: dict | None = None,
    ):
        """
        Initializes an instance of the `AsyncLLM` class.

        Parameters:
        - model (str): The model to be used for language generation.
        - base_url (str): The base URL for the OpenAI API.
        - organization_id (str, optional): The organization ID for the OpenAI API. Defaults to "z".
        - project_id (str, optional): The project ID for the OpenAI API. Defaults to "z".
        - llm_api_key (str, optional): The API key for the OpenAI API. Defaults to "z".
        - temperature (float, optional): What sampling temperature to use, between 0 and 2. Defaults to 1.0.
        - extra_body (dict, optional): Extra fields merged into the request body for provider-specific options. Defaults to None.
        """
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.extra_body = extra_body
        self.client = AsyncOpenAI(
            base_url=base_url,
            organization=organization_id,
            project=project_id,
            api_key=llm_api_key,
        )
        self.support_tools = True

        logger.info(
            f"Initialized AsyncLLM with the parameters: {self.base_url}, {self.model}"
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        system: str = None,
        tools: List[Dict[str, Any]] | NotGiven = NOT_GIVEN,
    ) -> AsyncIterator[str | List[ChoiceDeltaToolCall]]:
        """
        Generates a chat completion using the OpenAI API asynchronously.

        Parameters:
        - messages (List[Dict[str, Any]]): The list of messages to send to the API.
        - system (str, optional): System prompt to use for this completion.
        - tools (List[Dict[str, str]], optional): List of tools to use for this completion.

        Yields:
        - str: The content of each chunk from the API response.
        - List[ChoiceDeltaToolCall]: The tool calls detected in the response.

        Raises:
        - APIConnectionError: When the server cannot be reached
        - RateLimitError: When a 429 status code is received
        - APIError: For other API-related errors
        """
        stream = None
        # Tool call related state variables
        accumulated_tool_calls = {}
        in_tool_call = False
        # 會思考的模型有時只把答案放在 reasoning 欄位，content 一路是空的。
        # reasoning (delta.reasoning_content / delta.reasoning) and never emit
        # any visible content. Track whether we ever yielded non-empty content
        # so we can fall back to the buffered reasoning at stream end.
        yielded_content = False
        reasoning_buffer = ""

        try:
            # If system prompt is provided, add it to the messages
            messages_with_system = _drop_leading_assistant_turns(messages)
            if system:
                messages_with_system = [
                    {"role": "system", "content": system},
                    *messages_with_system,
                ]
            logger.debug(f"Messages: {messages_with_system}")

            available_tools = tools if self.support_tools else NOT_GIVEN

            create_kwargs = {
                "messages": messages_with_system,
                "model": self.model,
                "stream": True,
                "temperature": self.temperature,
                "tools": available_tools,
            }
            if self.extra_body is not None:
                create_kwargs["extra_body"] = self.extra_body

            stream: AsyncStream[
                ChatCompletionChunk
            ] = await self.client.chat.completions.create(**create_kwargs)
            logger.debug(
                f"Tool Support: {self.support_tools}, Available tools: {available_tools}"
            )

            async for chunk in stream:
                # 有些代理送出來的區塊沒有 choices 欄位，直接取用會炸。
                if not chunk.choices:
                    continue

                if self.support_tools:
                    has_tool_calls = (
                        hasattr(chunk.choices[0].delta, "tool_calls")
                        and chunk.choices[0].delta.tool_calls
                    )

                    if has_tool_calls:
                        logger.debug(
                            f"Tool calls detected in chunk: {chunk.choices[0].delta.tool_calls}"
                        )
                        in_tool_call = True
                        # Process tool calls in the current chunk
                        for tool_call in chunk.choices[0].delta.tool_calls:
                            index = (
                                tool_call.index if hasattr(tool_call, "index") else 0
                            )

                            # Initialize tool call for this index if needed
                            if index not in accumulated_tool_calls:
                                accumulated_tool_calls[index] = {
                                    "index": index,
                                    "id": getattr(tool_call, "id", None),
                                    "type": getattr(tool_call, "type", None),
                                    "function": {"name": "", "arguments": ""},
                                }

                            # Update tool call information
                            if hasattr(tool_call, "id") and tool_call.id:
                                accumulated_tool_calls[index]["id"] = tool_call.id
                            if hasattr(tool_call, "type") and tool_call.type:
                                accumulated_tool_calls[index]["type"] = tool_call.type

                            # Update function information
                            if hasattr(tool_call, "function"):
                                if (
                                    hasattr(tool_call.function, "name")
                                    and tool_call.function.name
                                ):
                                    accumulated_tool_calls[index]["function"][
                                        "name"
                                    ] = tool_call.function.name
                                if (
                                    hasattr(tool_call.function, "arguments")
                                    and tool_call.function.arguments
                                ):
                                    accumulated_tool_calls[index]["function"][
                                        "arguments"
                                    ] += tool_call.function.arguments

                        continue

                    # If we were in a tool call but now we're not, yield the tool call result
                    elif in_tool_call and not has_tool_calls:
                        in_tool_call = False
                        # Convert accumulated tool calls to the required format and output
                        logger.info(f"Complete tool calls: {accumulated_tool_calls}")

                        # Use the from_dict method to create a ToolCallObject instance from a dictionary
                        complete_tool_calls = [
                            ToolCallObject.from_dict(tool_data)
                            for tool_data in accumulated_tool_calls.values()
                        ]

                        yield complete_tool_calls
                        accumulated_tool_calls = {}  # Reset for potential future tool calls

                # 先把思考內容收著。它不一定用得到——只有 content 從頭到尾是空的時候才拿出來。
                # may not exist on the delta, so read them defensively.
                delta = chunk.choices[0].delta
                reasoning_chunk = getattr(delta, "reasoning_content", None) or getattr(
                    delta, "reasoning", None
                )
                if reasoning_chunk:
                    reasoning_buffer += reasoning_chunk

                # Process regular content chunks
                if len(chunk.choices) == 0:
                    logger.info("Empty chunk received")
                    continue
                elif chunk.choices[0].delta.content is None:
                    chunk.choices[0].delta.content = ""
                content = chunk.choices[0].delta.content
                if content:
                    yielded_content = True
                yield content

            # 整段都沒有可見內容時，退回去用思考欄位——有東西總比一片空白好。
            # content but did stream reasoning (a "thinking" model), surface the
            # reasoning as the reply so the character has something to say and
            # the TTS has text to speak. Strip <think>...</think> wrappers some
            # models emit around their reasoning.
            if not yielded_content and reasoning_buffer.strip():
                fallback = re.sub(
                    r"<think>.*?</think>", "", reasoning_buffer, flags=re.DOTALL
                ).strip()
                if not fallback:
                    fallback = reasoning_buffer.replace("<think>", "").replace(
                        "</think>", ""
                    ).strip()
                if fallback:
                    logger.info(
                        "No content streamed; falling back to buffered reasoning."
                    )
                    yield fallback

            # If stream ends while still in a tool call, make sure to yield the tool call
            if in_tool_call and accumulated_tool_calls:
                logger.info(f"Final tool call at stream end: {accumulated_tool_calls}")

                # Create a ToolCallObject instance from a dictionary using the from_dict method.
                complete_tool_calls = [
                    ToolCallObject.from_dict(tool_data)
                    for tool_data in accumulated_tool_calls.values()
                ]

                yield complete_tool_calls

        except APIConnectionError as e:
            logger.error(
                f"Error calling the chat endpoint: Connection error. Failed to connect to the LLM API. \nCheck the configurations and the reachability of the LLM backend. \nSee the logs for details. \nTroubleshooting with documentation: https://open-llm-vtuber.github.io/docs/faq#%E9%81%87%E5%88%B0-error-calling-the-chat-endpoint-%E9%94%99%E8%AF%AF%E6%80%8E%E4%B9%88%E5%8A%9E \n{e.__cause__}"
            )
            yield "Error calling the chat endpoint: Connection error. Failed to connect to the LLM API. Check the configurations and the reachability of the LLM backend. See the logs for details. Troubleshooting with documentation: [https://open-llm-vtuber.github.io/docs/faq#%E9%81%87%E5%88%B0-error-calling-the-chat-endpoint-%E9%94%99%E8%AF%AF%E6%80%8E%E4%B9%88%E5%8A%9E]"

        except RateLimitError as e:
            logger.error(
                f"Error calling the chat endpoint: Rate limit exceeded: {e.response}"
            )
            yield "Error calling the chat endpoint: Rate limit exceeded. Please try again later. See the logs for details."

        except APIError as e:
            if "does not support tools" in str(e):
                self.support_tools = False
                logger.warning(
                    f"{self.model} does not support tools. Disabling tool support."
                )
                yield "__API_NOT_SUPPORT_TOOLS__"
                return
            logger.error(f"LLM API: Error occurred: {e}")
            logger.info(f"Base URL: {self.base_url}")
            logger.info(f"Model: {self.model}")
            logger.info(f"Messages: {messages}")
            logger.info(f"temperature: {self.temperature}")
            yield "Error calling the chat endpoint: Error occurred while generating response. See the logs for details."

        finally:
            # make sure the stream is properly closed
            # so when interrupted, no more tokens will being generated.
            if stream:
                logger.debug("Chat completion finished.")
                await stream.close()
                logger.debug("Stream closed.")
