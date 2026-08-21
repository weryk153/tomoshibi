import os
import re
import json
import uuid
from datetime import datetime
from typing import Literal, List, TypedDict, Optional
from loguru import logger

from .llm_error_sentinel import is_llm_error_placeholder


class HistoryMessage(TypedDict):
    role: Literal["human", "ai"]
    timestamp: str
    content: str
    # Optional display information for the message
    name: Optional[str]
    avatar: Optional[str]
    # A message can carry a generated picture. Files written before this
    # existed have neither field; a missing type means "text".
    type: Optional[Literal["text", "image"]]
    image: Optional[str]


def _is_safe_filename(filename: str) -> bool:
    """Validate filename for safety and allowed characters"""
    if not filename or len(filename) > 255:
        return False

    # Allow alphanumeric, hyphen, underscore, and common unicode characters
    # Block any filesystem special characters, control characters, and path separators
    pattern = re.compile(r"^[\w\-_\u0020-\u007E\u00A0-\uFFFF]+$")
    return bool(pattern.match(filename))


def _sanitize_path_component(component: str) -> str:
    """Sanitize and validate a path component"""
    # Remove any path components, get just the basename
    sanitized = os.path.basename(component.strip())

    if not _is_safe_filename(sanitized):
        raise ValueError(f"Invalid characters in path component: {component}")

    return sanitized


def _ensure_conf_dir(conf_uid: str) -> str:
    """Ensure the directory for a specific conf exists and return its path"""
    if not conf_uid:
        raise ValueError("conf_uid cannot be empty")

    safe_conf_uid = _sanitize_path_component(conf_uid)
    base_dir = os.path.join("chat_history", safe_conf_uid)
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _get_safe_history_path(conf_uid: str, history_uid: str) -> str:
    """Get sanitized path for history file"""
    safe_conf_uid = _sanitize_path_component(conf_uid)
    safe_history_uid = _sanitize_path_component(history_uid)
    base_dir = os.path.join("chat_history", safe_conf_uid)
    full_path = os.path.normpath(os.path.join(base_dir, f"{safe_history_uid}.json"))
    if not full_path.startswith(base_dir):
        raise ValueError("Invalid path: Path traversal detected")
    return full_path


def create_new_history(conf_uid: str) -> str:
    """Create a new history file with a unique ID and return the history_uid"""
    if not conf_uid:
        logger.warning("No conf_uid provided")
        return ""

    # Use uuid.uuid4().hex to generate a UUID without hyphens
    # New format: UUID_YYYY-MM-DD_HH-MM-SS
    history_uid = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex}"
    conf_dir = _ensure_conf_dir(conf_uid)  # conf_uid is sanitized here

    # Create history file with empty metadata
    try:
        filepath = os.path.join(conf_dir, f"{history_uid}.json")
        initial_data = [
            {
                "role": "metadata",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to create new history file: {e}")
        return ""

    logger.debug(f"Created new history file with empty metadata: {filepath}")
    return history_uid


def store_message(
    conf_uid: str,
    history_uid: str,
    role: Literal["human", "ai"],
    content: str,
    name: str | None = None,
    avatar: str | None = None,
    display_content: str | None = None,
    message_type: str = "text",
    image: str | None = None,
):
    """Store a message in a specific history file

    Args:
        conf_uid: Configuration unique identifier
        history_uid: History unique identifier
        role: Message role ("human" or "ai")
        content: Message content
        name: Optional display name (default None)
        avatar: Optional avatar URL (default None)
        display_content: Optional translated text shown by the UI. ``content``
            remains the canonical text used as LLM conversation context.
        message_type: "text" (default) or "image".
        image: URL path of a generated picture, for message_type="image".
    """
    if not conf_uid or not history_uid:
        if not conf_uid:
            logger.warning("Missing conf_uid")
        if not history_uid:
            logger.warning("Missing history_uid")
        return

    # A failed chat completion is yielded as an English sentence rather than
    # raised (see llm_error_sentinel), so it arrives here looking like something
    # the character said. Persisting it means the user sees it on reload and any
    # later turn reads it back as conversation context. It is a backend failure
    # notice, not a turn — keep it out of the transcript. Measured before this
    # guard: 75 such entries across 9 history files.
    if role == "ai" and is_llm_error_placeholder(content):
        logger.warning(
            "Refusing to store an LLM error placeholder as an assistant turn"
        )
        return

    filepath = _get_safe_history_path(conf_uid, history_uid)
    logger.debug(f"Storing {role} message to {filepath}")

    history_data = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            logger.error(f"Failed to load history file: {filepath}")
            pass

    now_str = datetime.now().isoformat(timespec="seconds")
    new_item = {
        "role": role,
        "timestamp": now_str,
        "content": content,
        "type": message_type,
        "image": image,
    }

    # Add optional display information if provided
    if name is not None:
        new_item["name"] = name
    if avatar is not None:
        new_item["avatar"] = avatar
    if display_content and display_content != content:
        new_item["display_content"] = display_content

    history_data.append(new_item)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    logger.debug(f"Successfully stored {role} message")


def get_metadata(conf_uid: str, history_uid: str) -> dict:
    """Get metadata from history file"""
    if not conf_uid or not history_uid:
        return {}

    filepath = _get_safe_history_path(conf_uid, history_uid)
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            history_data = json.load(f)

        if history_data and history_data[0]["role"] == "metadata":
            return history_data[0]
    except Exception as e:
        logger.error(f"Failed to get metadata: {e}")
    return {}


def update_metadate(conf_uid: str, history_uid: str, metadata: dict) -> bool:
    """Set metadata in history file

    Updates existing metadata with new fields, preserving existing ones.
    If no metadata exists, creates new metadata entry.
    """
    if not conf_uid or not history_uid:
        return False

    filepath = _get_safe_history_path(conf_uid, history_uid)
    if not os.path.exists(filepath):
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            history_data = json.load(f)

        if history_data and history_data[0]["role"] == "metadata":
            # Update existing metadata while preserving other fields
            history_data[0].update(metadata)
        else:
            # Create new metadata with timestamp if none exists
            new_metadata = {
                "role": "metadata",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            new_metadata.update(metadata)  # Add new fields
            history_data.insert(0, new_metadata)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Updated metadata for history {history_uid}")
        return True
    except Exception as e:
        logger.error(f"Failed to set metadata: {e}")
    return False


def get_history(conf_uid: str, history_uid: str) -> List[HistoryMessage]:
    """Read chat history for the given conf_uid and history_uid"""
    if not conf_uid or not history_uid:
        if not conf_uid:
            logger.warning("Missing conf_uid")
        if not history_uid:
            logger.warning("Missing history_uid")
        return []

    filepath = _get_safe_history_path(conf_uid, history_uid)

    if not os.path.exists(filepath):
        logger.warning(f"History file not found: {filepath}")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            history_data = json.load(f)
            # Filter out metadata
            messages = [msg for msg in history_data if msg["role"] != "metadata"]
            # 補上 id。前端的 Message 型別把它標成必填、訊息列表用 key={msg.id}
            # 渲染，但歷史檔裡從來沒有這個欄位——每一則的 key 都是 undefined。
            # 初次載入只是掛載，重複的 key 頂多警告；但要「替換一個已經有內容的
            # 列表」時（另一台裝置發話後把更新後的紀錄推過來）React 會直接崩：
            # NotFoundError: Failed to execute 'removeChild' on 'Node'，整個畫面
            # 變全白。
            #
            # 補在讀取而不是寫入：既有的歷史檔都沒有這個欄位，補在寫入端只能救
            # 新訊息，舊對話照樣會炸。用序號當基底而不是內容或時間——同一秒內
            # 連送兩則一模一樣的訊息是做得到的（重複點送出、主動發言重試），
            # 撞在一起就又變成同一個 key。紀錄是唯讀且只追加的，序號因此穩定。
            for index, msg in enumerate(messages):
                if not msg.get("id"):
                    msg["id"] = f"{history_uid}-{index}"
            return messages
    except Exception:
        return []


def history_exists(conf_uid: str, history_uid: str) -> bool:
    """Report whether a history file is still on disk.

    ``get_history`` returns ``[]`` both for a deleted conversation and for one
    that simply has no messages yet, so callers deciding whether a remembered
    conversation can be resumed need this distinction.
    """
    if not conf_uid or not history_uid:
        return False

    try:
        return os.path.exists(_get_safe_history_path(conf_uid, history_uid))
    except ValueError:
        return False


def delete_history(conf_uid: str, history_uid: str) -> bool:
    """Delete a specific history file"""
    if not conf_uid or not history_uid:
        logger.warning("Missing conf_uid or history_uid")
        return False

    filepath = _get_safe_history_path(conf_uid, history_uid)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Successfully deleted history file: {filepath}")
            return True
    except Exception as e:
        logger.error(f"Failed to delete history file: {e}")
    return False


def get_history_list(conf_uid: str) -> List[dict]:
    """Get list of histories with their latest messages"""
    if not conf_uid:
        return []

    histories = []
    conf_dir = _ensure_conf_dir(conf_uid)
    empty_history_uids = []

    try:
        for filename in os.listdir(conf_dir):
            if not filename.endswith(".json"):
                continue

            history_uid = filename[:-5]
            filepath = os.path.join(conf_dir, filename)

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    messages = json.load(f)

                    # Filter out metadata for checking if history is empty
                    actual_messages = [
                        msg for msg in messages if msg["role"] != "metadata"
                    ]
                    if not actual_messages:
                        empty_history_uids.append(history_uid)
                        continue

                    latest_message = dict(actual_messages[-1])
                    if latest_message.get("display_content"):
                        latest_message["content"] = latest_message["display_content"]
                    history_info = {
                        "uid": history_uid,
                        "latest_message": latest_message,
                        "timestamp": (
                            latest_message["timestamp"] if latest_message else None
                        ),
                    }
                    histories.append(history_info)
            except Exception as e:
                logger.error(f"Error reading history file {filename}: {e}")
                continue

        # Clean up empty histories if there are other non-empty ones
        if len(empty_history_uids) > 0 and len(os.listdir(conf_dir)) > 1:
            for uid in empty_history_uids:
                try:
                    os.remove(os.path.join(conf_dir, f"{uid}.json"))
                    logger.info(f"Removed empty history file: {uid}")
                except Exception as e:
                    logger.error(f"Failed to remove empty history file {uid}: {e}")

        histories.sort(
            key=lambda x: x["timestamp"] if x["timestamp"] else "", reverse=True
        )
        return histories

    except Exception as e:
        logger.error(f"Error listing histories: {e}")
        return []


def modify_latest_message(
    conf_uid: str,
    history_uid: str,
    role: Literal["human", "ai", "system"],
    new_content: str,
) -> bool:
    """Modify the latest message in a specific history file if it matches the given role"""
    if not conf_uid or not history_uid:
        logger.warning("Missing conf_uid or history_uid")
        return False

    filepath = _get_safe_history_path(conf_uid, history_uid)
    if not os.path.exists(filepath):
        logger.warning(f"History file not found: {filepath}")
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            history_data = json.load(f)

        if not history_data:
            logger.warning("History is empty")
            return False

        latest_message = history_data[-1]
        if latest_message["role"] != role:
            logger.warning(
                f"Latest message role ({latest_message['role']}) doesn't match requested role ({role})"
            )
            return False

        latest_message["content"] = new_content
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Successfully modified latest {role} message")
        return True

    except Exception as e:
        logger.error(f"Failed to modify latest message: {e}")
        return False


def rename_history_file(
    conf_uid: str, old_history_uid: str, new_history_uid: str
) -> bool:
    """Rename a history file with a new history_uid"""
    if not conf_uid or not old_history_uid or not new_history_uid:
        logger.warning("Missing required parameters for rename")
        return False

    old_filepath = _get_safe_history_path(conf_uid, old_history_uid)
    new_filepath = _get_safe_history_path(conf_uid, new_history_uid)

    try:
        if os.path.exists(old_filepath):
            os.rename(old_filepath, new_filepath)
            logger.info(
                f"Renamed history file from {old_history_uid} to {new_history_uid}"
            )
            return True
    except Exception as e:
        logger.error(f"Failed to rename history file: {e}")
    return False
