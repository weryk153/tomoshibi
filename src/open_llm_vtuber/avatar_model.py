import json
import chardet
from loguru import logger

# This class will only prepare the payload for the live2d model
# the process of sending the payload should be done by the caller
# This class is **Not responsible** for sending the payload to the server


def normalize_tap_motions(raw) -> dict:
    """Normalize every hit area's value to ``[{group, index, weight}, ...]``.

    Two shapes exist in the wild:
    - legacy (object): ``{"TapBody": 2}`` — maps group name -> weight, with no
      specific motion index (a random motion within the group is chosen at
      runtime). Converts to ``[{"group": "TapBody", "index": None, "weight": 2}]``.
    - current (list): already ``[{"group", "index", "weight"}, ...]`` — items
      are coerced/defaulted but otherwise passed through.
    """
    result: dict = {}
    if not isinstance(raw, dict):
        return result
    for area_id, value in raw.items():
        if isinstance(value, list):
            normalized = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "group": item.get("group", ""),
                        "index": item.get("index"),
                        "weight": item.get("weight", 1),
                    }
                )
            result[area_id] = normalized
        elif isinstance(value, dict):
            # Legacy object shape: {group_name: weight, ...}. No index was ever
            # recorded for this shape, so it stays None.
            result[area_id] = [
                {"group": group, "index": None, "weight": weight}
                for group, weight in value.items()
            ]
        else:
            result[area_id] = []
    return result


class AvatarModel:
    """
    A class to represent the character's avatar model (Live2D or VRM). This class only prepares and stores the information of the avatar model. It does not send anything to the frontend or server or anything.

    Attributes:
        model_dict_path (str): The path to the model dictionary file.
        live2d_model_name (str): The name of the Live2D model.
        model_info (dict): The information of the Live2D model.
        emo_map (dict): The emotion map of the Live2D model.
        emo_str (str): The string representation of the emotion map of the Live2D model.
        motion_map (dict): The motion map of the Live2D model. Empty if the model dict
            entry has no `motionMap` field.
        motion_str (str): The string representation of the motion map of the Live2D model.
    """

    model_dict_path: str
    live2d_model_name: str
    model_info: dict
    emo_map: dict
    emo_str: str
    motion_map: dict
    motion_str: str
    stage_performance_ids: set[str]

    def __init__(
        self, live2d_model_name: str, model_dict_path: str = "model_dict.json"
    ):
        self.model_dict_path: str = model_dict_path
        self.live2d_model_name: str = live2d_model_name
        self.stage_performance_ids = set()
        self.set_model(live2d_model_name)

    def set_model(self, model_name: str) -> None:
        """
        Set the model with its name and load the model information. This method will initialize the `self.model_info`, `self.emo_map`, and `self.emo_str` attributes.
        This method is called in the constructor.

        Parameters:
            model_name (str): The name of the live2d model.

            Returns:
            None
        """

        self.model_info: dict = self._lookup_model_info(model_name)

        # tapMotions is normalized HERE, at the single source of truth, because
        # `model_info` is sent to the frontend verbatim by websocket_handler
        # (`set-model-and-conf`). The frontend's tap selection only understands
        # the list shape; handing it the legacy `{group: weight}` object throws
        # a TypeError inside the mouseup handler, which breaks tapping entirely
        # and also skips the handler's own cleanup. Normalizing only inside the
        # settings endpoint left every on-disk model broken until the user
        # happened to open that page and save.
        self.model_info["tapMotions"] = normalize_tap_motions(
            self.model_info.get("tapMotions", {})
        )

        self.emo_map: dict = {
            k.lower(): v for k, v in self.model_info["emotionMap"].items()
        }
        self.emo_str: str = " ".join([f"[{key}]," for key in self.emo_map.keys()])
        # emo_str is a string of the keys in the emoMap dictionary. The keys are enclosed in square brackets.
        # example: `"[fear], [anger], [disgust], [sadness], [joy], [neutral], [surprise]"`

        self.motion_map: dict = {
            k.lower(): v for k, v in self.model_info.get("motionMap", {}).items()
        }
        # motion_str mirrors emo_str's format, but appends each motion's `label`
        # when it has one. The keyword alone (`gesture_1`) tells the LLM nothing
        # about what the animation depicts, so it cannot choose between six of
        # them; the label is what makes the choice meaningful. Motions whose
        # label is still unknown are listed bare, which reads to the LLM as
        # "unspecified" rather than as a wrong description.
        # example: `"[special_1]（雙手畫圓）, [gesture_1],"`
        self.motion_str: str = " ".join(
            [
                f"[{key}]（{value['label']}）," if value.get("label") else f"[{key}],"
                for key, value in self.motion_map.items()
            ]
        )

    @property
    def type(self) -> str:
        """``live2d`` 或 ``vrm``。舊的 model_dict.json 項目沒有這欄，缺省是 live2d。"""
        return self.model_info.get("type", "live2d")

    def _load_file_content(self, file_path: str) -> str:
        """Load the content of a file with robust encoding handling."""
        # Try common encodings first
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "ascii"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue

        # If all common encodings fail, try to detect encoding
        try:
            with open(file_path, "rb") as file:
                raw_data = file.read()
            detected = chardet.detect(raw_data)
            detected_encoding = detected["encoding"]

            if detected_encoding:
                try:
                    return raw_data.decode(detected_encoding)
                except UnicodeDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Error detecting encoding for {file_path}: {e}")

        raise UnicodeError(f"Failed to decode {file_path} with any encoding")

    def _lookup_model_info(self, model_name: str) -> dict:
        """
        Find the model information from the model dictionary and return the information about the matched model.

        Parameters:
            model_name (str): The name of the live2d model.

        Returns:
            dict: The dictionary with the information of the matched model.

        Raises:
            FileNotFoundError if the model dictionary file is not found.

            json.JSONDecodeError if the model dictionary file is not a valid JSON file.

            KeyError if the model name is not found in the model dictionary.

        """

        self.live2d_model_name = model_name

        try:
            file_content = self._load_file_content(self.model_dict_path)
            model_dict = json.loads(file_content)
        except FileNotFoundError as file_e:
            logger.critical(
                f"Model dictionary file not found at {self.model_dict_path}."
            )
            raise file_e
        except json.JSONDecodeError as json_e:
            logger.critical(
                f"Error decoding JSON from model dictionary file at {self.model_dict_path}."
            )
            raise json_e
        except UnicodeError as uni_e:
            logger.critical(
                f"Error reading model dictionary file at {self.model_dict_path}."
            )
            raise uni_e
        except Exception as e:
            logger.critical(
                f"Error occurred while reading model dictionary file at {self.model_dict_path}."
            )
            raise e

        # Find the model in the model_dict
        matched_model = next(
            (model for model in model_dict if model["name"] == model_name), None
        )

        if matched_model is None:
            logger.critical(f"Unable to find {model_name} in {self.model_dict_path}.")
            raise KeyError(
                f"{model_name} not found in model dictionary {self.model_dict_path}."
            )

        # The feature: "translate model url to full url if it starts with '/' " is no longer implemented here

        logger.info("Model Information Loaded.")

        return matched_model

    def _scan_emotion_keys(self, str_to_check: str) -> list:
        """掃出字串裡出現過的情緒關鍵字（名字，不是索引），依出現順序。

        extract_emotion 回傳的是表情索引，那是前端要的；語音要的是名字——
        參考音檔的對照表以人看得懂的關鍵字為 key（見 gpt_sovits_tts）。用索引
        反查名字會有歧義（多個關鍵字可以指向同一個表情），所以掃描時就把名字
        留下來，不要繞一圈再倒推。
        """
        keys = []
        str_to_check = str_to_check.lower()
        i = 0
        while i < len(str_to_check):
            if str_to_check[i] != "[":
                i += 1
                continue
            for key in self.emo_map.keys():
                emo_tag = f"[{key}]"
                if str_to_check[i : i + len(emo_tag)] == emo_tag:
                    keys.append(key)
                    i += len(emo_tag) - 1
                    break
            i += 1
        return keys

    def extract_emotion_keys(self, str_to_check: str) -> list:
        """公開版的關鍵字掃描；語音那條路徑用它挑參考音。"""
        return self._scan_emotion_keys(str_to_check)

    def extract_emotion(self, str_to_check: str) -> list:
        """
        Check the input string for any emotion keywords and return a list of values (the expression index) of the emotions found in the string.

        Parameters:
            str_to_check (str): The string to check for emotions.

        Returns:
            list: A list of values of the emotions found in the string. An empty list is returned if no emotions are found.
        """

        expression_list = []
        str_to_check = str_to_check.lower()

        i = 0
        while i < len(str_to_check):
            if str_to_check[i] != "[":
                i += 1
                continue
            for key in self.emo_map.keys():
                emo_tag = f"[{key}]"
                if str_to_check[i : i + len(emo_tag)] == emo_tag:
                    expression_list.append(self.emo_map[key])
                    i += len(emo_tag) - 1
                    break
            i += 1
        return expression_list

    def extract_motions(self, str_to_check: str) -> list:
        """
        Check the input string for any motion keywords and return a list of values
        (the {"group", "index"} dict) of the motions found in the string, in the
        order they appear.

        Parameters:
            str_to_check (str): The string to check for motions.

        Returns:
            list: A list of {"group", "index"} dicts for the motions found in the
            string. An empty list is returned if no motions are found.
        """

        motion_list = []
        str_to_check = str_to_check.lower()

        i = 0
        while i < len(str_to_check):
            if str_to_check[i] != "[":
                i += 1
                continue
            for key in self.motion_map.keys():
                motion_tag = f"[{key}]"
                if str_to_check[i : i + len(motion_tag)] == motion_tag:
                    # 只回傳前端播放需要的兩個欄位。`label` 是給 prompt 與設定頁
                    # 看的，把它一起送到 WebSocket 上只會讓契約多一個沒人用的欄位。
                    value = self.motion_map[key]
                    if "clip" in value:
                        # VRM：一個 .vrma 檔名就是一個動作，沒有 group/index。
                        motion_list.append({"clip": value["clip"]})
                    else:
                        motion_list.append(
                            {"group": value["group"], "index": value["index"]}
                        )
                    i += len(motion_tag) - 1
                    break
            i += 1
        return motion_list

    def remove_emotion_keywords(self, target_str: str) -> str:
        """
        Remove the emotion keywords from the input string and return the cleaned string.

        Parameters:
            str_to_check (str): The string to check for emotions.

        Returns:
            str: The cleaned string with the emotion keywords removed.
        """

        lower_str = target_str.lower()

        for key in self.emo_map.keys():
            lower_key = f"[{key}]".lower()
            while lower_key in lower_str:
                start_index = lower_str.find(lower_key)
                end_index = start_index + len(lower_key)
                target_str = target_str[:start_index] + target_str[end_index:]
                lower_str = lower_str[:start_index] + lower_str[end_index:]
        return target_str
