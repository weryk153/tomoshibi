#!/usr/bin/env python3
"""產生一個無縫循環的待機動畫（.vrma），不依賴任何既有的動作素材。

**為什麼需要這支**

VRM 的靜止姿勢是 T-pose。`motion-player.ts` 沒有 idle action 時會淡出到那個姿勢，
角色就直接張成大字——所以 `motions/idle.vrma` 形同必要，不是選用的。

而現成的 `.vrma` 幾乎都是一次性的情緒動作（三、四秒，起訖姿勢不同）。拿它們當
idle 會有兩個問題：`LoopRepeat` 從末幀硬接回首幀，每隔幾秒彈一下；而且擺幅通常
太大，角色會一直揮舞。

這支從零生成：自己搭一副標準人形骨架、自己算曲線，所以產出的檔案沒有第三方素材
的授權問題，可以隨專案散布。

**怎麼做到無縫**

所有頻率都取週期的整數倍，於是 t=0 與 t=PERIOD 的取值完全相同，接回去不會跳。

用法：
    python scripts/make_idle_vrma.py vrm-models/<模型名>/motions/idle.vrma
"""

import json
import math
import struct
import sys

PERIOD = 6.0   # 秒。所有擺動頻率都是 1/PERIOD 的整數倍
FPS = 30

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

# 一副標準的 VRM T-pose 骨架：(骨頭名, 父骨頭, 相對父骨頭的位移／公尺)。
# 這是 VRM 規格要求的人形結構與大致人體比例，不是誰的創作。手臂沿 ±X 伸直
# 就是 T-pose 的定義；hips 的高度要大於 0，否則 three-vrm 會警告違反 T-pose。
SKELETON = [
    ("hips",          None,          (0.00,  0.90,  0.00)),
    ("spine",         "hips",        (0.00,  0.10,  0.00)),
    ("chest",         "spine",       (0.00,  0.12,  0.00)),
    ("upperChest",    "chest",       (0.00,  0.12,  0.00)),
    ("neck",          "upperChest",  (0.00,  0.12,  0.00)),
    ("head",          "neck",        (0.00,  0.07,  0.00)),
    ("leftShoulder",  "upperChest",  (0.05,  0.08,  0.00)),
    ("leftUpperArm",  "leftShoulder", (0.10, 0.00,  0.00)),
    ("leftLowerArm",  "leftUpperArm", (0.25, 0.00,  0.00)),
    ("leftHand",      "leftLowerArm", (0.24, 0.00,  0.00)),
    ("rightShoulder", "upperChest",  (-0.05, 0.08,  0.00)),
    ("rightUpperArm", "rightShoulder", (-0.10, 0.00, 0.00)),
    ("rightLowerArm", "rightUpperArm", (-0.25, 0.00, 0.00)),
    ("rightHand",     "rightLowerArm", (-0.24, 0.00, 0.00)),
    ("leftUpperLeg",  "hips",        (0.08, -0.05,  0.00)),
    ("leftLowerLeg",  "leftUpperLeg", (0.00, -0.40, 0.00)),
    ("leftFoot",      "leftLowerLeg", (0.00, -0.40, 0.00)),
    ("leftToes",      "leftFoot",    (0.00, -0.06,  0.10)),
    ("rightUpperLeg", "hips",        (-0.08, -0.05, 0.00)),
    ("rightLowerLeg", "rightUpperLeg", (0.00, -0.40, 0.00)),
    ("rightFoot",     "rightLowerLeg", (0.00, -0.40, 0.00)),
    ("rightToes",     "rightFoot",   (0.00, -0.06,  0.10)),
]

# 基準姿勢：把 T-pose 的手臂放下來。角度是相對 T-pose 的，繞 Z 軸轉。
# 左臂沿 +X，往 -Z 方向轉（負角）就會朝下；右臂沿 -X，方向相反。
REST = {
    "leftUpperArm":  [("z", -72.0)],
    "rightUpperArm": [("z",  72.0)],
    "leftLowerArm":  [("z", -10.0), ("y", -6.0)],   # 手肘微彎，手掌略往身前
    "rightLowerArm": [("z",  10.0), ("y",  6.0)],
    "leftShoulder":  [("z",  -4.0)],
    "rightShoulder": [("z",   4.0)],
    "leftHand":      [("z",  -5.0)],
    "rightHand":     [("z",   5.0)],
}

# 疊在基準姿勢上的擺動：(軸, 振幅／度, 每週期幾次, 相位)。
# 呼吸取 2 次／週期（一次約三秒），重心與頭部取 1 次，錯開相位免得整個人同步晃。
SWAY = {
    "spine":         [("x",  1.0, 2, 0.00)],
    "chest":         [("x",  1.2, 2, 0.00)],
    "upperChest":    [("x",  0.9, 2, 0.00)],
    "neck":          [("x", -0.7, 2, 0.00), ("y", 1.0, 1, 0.25)],
    "head":          [("x", -0.7, 2, 0.00), ("y", 1.8, 1, 0.00)],
    "leftShoulder":  [("z",  0.8, 2, 0.00)],
    "rightShoulder": [("z", -0.8, 2, 0.00)],
    "leftUpperArm":  [("z",  1.4, 1, 0.15)],
    "rightUpperArm": [("z", -1.4, 1, 0.15)],
    "hips":          [("y",  0.7, 1, 0.00)],
}


def axis_angle(axis: str, deg: float) -> tuple:
    """繞單一軸的四元數，(x, y, z, w)。"""
    h = math.radians(deg) / 2.0
    s, c = math.sin(h), math.cos(h)
    return {"x": (s, 0.0, 0.0, c), "y": (0.0, s, 0.0, c), "z": (0.0, 0.0, s, c)}[axis]


def qmul(a: tuple, b: tuple) -> tuple:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def compose(specs) -> tuple:
    q = (0.0, 0.0, 0.0, 1.0)
    for axis, deg in specs:
        q = qmul(q, axis_angle(axis, deg))
    return q


def build() -> bytes:
    names = [b[0] for b in SKELETON]
    index = {n: i for i, n in enumerate(names)}
    children = {n: [] for n in names}
    for name, parent, _ in SKELETON:
        if parent is not None:
            children[parent].append(index[name])

    nodes = []
    for name, _parent, offset in SKELETON:
        node = {"name": name, "translation": list(offset)}
        if children[name]:
            node["children"] = children[name]
        nodes.append(node)

    frames = int(PERIOD * FPS) + 1          # 含首尾兩端
    times = [i / FPS for i in range(frames)]

    out = bytearray()
    buffer_views, accessors, samplers, channels = [], [], [], []

    def push(values, ncomp, typ):
        while len(out) % 4:
            out.append(0)
        offset = len(out)
        flat = [c for v in values for c in v] if ncomp > 1 else list(values)
        out.extend(struct.pack("<%df" % len(flat), *flat))
        buffer_views.append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(flat) * 4}
        )
        acc = {
            "bufferView": len(buffer_views) - 1,
            "componentType": 5126,
            "count": len(values),
            "type": typ,
        }
        if typ == "SCALAR":                  # glTF 要求 input 帶 min/max
            acc["min"], acc["max"] = [min(flat)], [max(flat)]
        accessors.append(acc)
        return len(accessors) - 1

    t_acc = push(times, 1, "SCALAR")

    for name in names:
        rest = compose(REST.get(name, []))
        sway = SWAY.get(name, [])
        if not sway and name not in REST:
            continue                          # 這根骨頭整段不動，不必產生軌道
        keys = []
        for t in times:
            q = rest
            for axis, deg, cycles, phase in sway:
                a = deg * math.sin(2 * math.pi * (cycles * t / PERIOD + phase))
                q = qmul(q, axis_angle(axis, a))
            keys.append(q)
        out_acc = push(keys, 4, "VEC4")
        samplers.append({"input": t_acc, "output": out_acc, "interpolation": "LINEAR"})
        channels.append(
            {"sampler": len(samplers) - 1,
             "target": {"node": index[name], "path": "rotation"}}
        )

    doc = {
        "asset": {"version": "2.0", "generator": "Tomoshibi make_idle_vrma.py"},
        "extensionsUsed": ["VRMC_vrm_animation"],
        "extensions": {
            "VRMC_vrm_animation": {
                "specVersion": "1.0",
                "humanoid": {
                    "humanBones": {n: {"node": index[n]} for n in names}
                },
            }
        },
        "scene": 0,
        "scenes": [{"nodes": [index["hips"]]}],
        "nodes": nodes,
        "buffers": [{"byteLength": len(out)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "animations": [{"name": "idle", "channels": channels, "samplers": samplers}],
    }

    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    out.extend(b"\0" * (-len(out) % 4))

    glb = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(out))
    glb += struct.pack("<II", len(js), JSON_CHUNK) + js
    glb += struct.pack("<II", len(out), BIN_CHUNK) + bytes(out)
    return glb


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    data = build()
    with open(sys.argv[1], "wb") as f:
        f.write(data)
    print(f"寫出 {sys.argv[1]}：{len(data)} bytes，{PERIOD} 秒 / {FPS} fps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
