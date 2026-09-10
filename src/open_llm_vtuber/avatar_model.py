import json
import re

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

    # [關鍵字] 或 [關鍵字:強度]。強度 0..1，沒寫就是 1.0。
    #
    # 原本四個地方各寫一份逐字元的比對迴圈（掃情緒、掃名字、掃動作、清關鍵字），
    # 加一個語法就要同步改四份、漏一份不會有錯誤訊息——只是那個地方悄悄失效。
    # 全部收斂到這裡。
    _TAG_RE = re.compile(r"\[([^\[\]]{1,64})\]")

    @staticmethod
    def _parse_tag(body: str) -> tuple:
        """把方括號裡的內容拆成 (關鍵字, 強度)。"""
        key, _, raw = body.partition(":")
        key = key.strip()
        if not raw:
            return key, 1.0
        try:
            # 夾在 0..1：LLM 給 1.5 或 -0.3 的話照收會讓權重爆掉。
            return key, max(0.0, min(1.0, float(raw.strip())))
        except ValueError:
            # [joy:超開心] 這種寫不出數字的情況，當作沒指定強度而不是丟掉整個標籤
            # ——關鍵字本身仍然是使用者要的表達。
            return key, 1.0

    def _scan_tags(self, str_to_check: str, keys) -> list:
        """依出現順序回傳 [(關鍵字, 強度)]，只留 keys 裡認得的。"""
        found = []
        for match in self._TAG_RE.finditer(str_to_check.lower()):
            key, intensity = self._parse_tag(match.group(1))
            if key in keys:
                found.append((key, intensity))
        return found

    def _scan_emotion_keys(self, str_to_check: str) -> list:
        """掃出字串裡出現過的情緒關鍵字（名字，不是索引），依出現順序。

        extract_emotion 回傳的是表情索引，那是前端要的；語音要的是名字——
        參考音檔的對照表以人看得懂的關鍵字為 key（見 gpt_sovits_tts）。用索引
        反查名字會有歧義（多個關鍵字可以指向同一個表情），所以掃描時就把名字
        留下來，不要繞一圈再倒推。
        """
        return [key for key, _ in self._scan_tags(str_to_check, self.emo_map)]

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

        return [
            self.emo_map[key] for key, _ in self._scan_tags(str_to_check, self.emo_map)
        ]

    def extract_emotion_intensities(self, str_to_check: str) -> list:
        """跟 extract_emotion 一一對應的強度清單（0..1）。

        強度只有 VRM 用得到——它的表情是連續權重。Live2D 的表情是一個個獨立的
        檔案，沒有「七成的笑」這種東西，所以那邊會忽略這個清單。刻意做成平行的
        兩個清單而不是改 extract_emotion 的元素型別：後者會動到 Live2D 那整條
        路徑，而它根本用不到強度。
        """
        return [i for _, i in self._scan_tags(str_to_check, self.emo_map)]

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
        for key, intensity in self._scan_tags(str_to_check, self.motion_map):
            # 只回傳前端播放需要的欄位。`label` 是給 prompt 與設定頁看的，把它一起
            # 送到 WebSocket 上只會讓契約多一個沒人用的欄位。
            value = self.motion_map[key]
            if "clip" in value:
                # VRM：一個 .vrma 檔名就是一個動作，沒有 group/index。
                motion = {"clip": value["clip"]}
            else:
                motion = {"group": value["group"], "index": value["index"]}
            # 動作本來就是 dict，強度直接掛進去，不必再開一條平行清單。
            # Live2D 沒有動作權重的概念，那邊會忽略它。
            if intensity != 1.0:
                motion["intensity"] = intensity
            motion_list.append(motion)
        return motion_list

    def remove_emotion_keywords(self, target_str: str) -> str:
        """
        Remove the emotion keywords from the input string and return the cleaned string.

        Parameters:
            str_to_check (str): The string to check for emotions.

        Returns:
            str: The cleaned string with the emotion keywords removed.
        """

        # 從後往前刪，前面的位移才不會被後面的刪除影響。認得 [joy] 也認得
        # [joy:0.4]——漏掉帶強度的寫法，那串標籤就會被原封不動唸出來。
        for match in reversed(list(self._TAG_RE.finditer(target_str.lower()))):
            key, _ = self._parse_tag(match.group(1))
            if key in self.emo_map:
                target_str = target_str[: match.start()] + target_str[match.end() :]
        return target_str
