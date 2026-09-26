#!/usr/bin/env python3
"""
プログラムモードの案内音声を ElevenLabs で作る（声＝リョウ・eleven_v3。書籍のAI音読と同じ）。

  python3 tools/make_voice.py          … 見積もりだけ（0クレジット）
  python3 tools/make_voice.py --go     … 作る → 1本ずつ書き取って台本と照合 → ずれたら作り直す（最大3回）

🔴 短い断片を1本ずつ作ると、先頭の1音が落ちることがある（~/.claude/skills/ai-onodoku）。
   だから文頭に「それでは、」「はい、」を置き、作ったら必ず書き取って確かめる。
🔴 目の語（右目・左目・両目）はかなで書く（「うもく」等と読ませないため）。
"""
import base64, difflib, json, os, re, subprocess, sys, urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "voice"
VOICE, MODEL = "1cOJcfrlMmUCGpeJbXg9", "eleven_v3"

# id, 読ませる文, 照合に使う読み（ひらがな）
LINES = [
    ("intro",    "これから、目のトレーニングをはじめます。",
                 "これから、めのとれーにんぐをはじめます"),
    ("both",     "それでは、りょうめで見てください。",
                 "それでは、りょうめでみてください"),
    ("right",    "それでは、ひだりめを手でかくして、みぎめだけで見てください。",
                 "それでは、ひだりめをてでかくして、みぎめだけでみてください"),
    ("left",     "それでは、みぎめを手でかくして、ひだりめだけで見てください。",
                 "それでは、みぎめをてでかくして、ひだりめだけでみてください"),
    ("endcover", "はい、そこまでです。手をおろしてください。",
                 "はい、そこまでです。てをおろしてください"),
    ("end",      "はい、そこまでです。",
                 "はい、そこまでです"),
    ("finish",   "おつかれさまでした。これでおわりです。",
                 "おつかれさまでした。これでおわりです"),
]

def norm(s):
    s = re.sub(r"[^ぁ-んー]", "", s)
    return s.replace("ー", "")

def tts(text, path):
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    path.write_bytes(urllib.request.urlopen(req, timeout=120).read())

def hear(path):
    small = Path("/tmp") / f"sq_{path.stem}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
                    "-af", "adelay=400:all=1,apad=pad_dur=0.4",
                    "-ac", "1", "-ar", "16000", "-b:a", "32k", str(small)], check=True)
    b64 = base64.b64encode(small.read_bytes()).decode()
    body = {"model": "gpt-audio", "modalities": ["text"], "messages": [
        {"role": "system", "content": "あなたは発音を書き取る係です。聞こえた音を、ひらがなだけで書き取ります。"
                                      "漢字・カタカナ・英字は一切使いません。意味で直さず、実際に発音された音のとおりに書きます。"},
        {"role": "user", "content": [
            {"type": "text", "text": "音声はこのメッセージに添付済みです。前置きを書かず、ひらがなの書き取りだけを返してください。"},
            {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3"}}]}]}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
                                          "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["message"]["content"].strip()

def main():
    chars = sum(len(t) for _, t, _ in LINES)
    print(f"{len(LINES)}本・{chars}字 → 約{(chars + 1) // 2}クレジット（v3は2字で1）×作り直しの回数")
    if "--go" not in sys.argv:
        print("（--go を付けるまで作らない）"); return
    OUT.mkdir(parents=True, exist_ok=True)
    for vid, text, kana in LINES:
        p = OUT / f"{vid}.mp3"
        for n in range(1, 4):
            tts(text, p)
            got = hear(p)
            r = difflib.SequenceMatcher(None, norm(got), norm(kana)).ratio()
            head_ok = norm(got)[:3] == norm(kana)[:3]
            ok = r >= 0.9 and head_ok
            print(f"{vid:9} {n}回目 {'✓' if ok else '✗'} 一致{r:.2f} 書き取り「{got}」")
            if ok: break
        else:
            print(f"  🔴 {vid} は3回とも台本とずれた。耳で確かめること")

if __name__ == "__main__":
    main()
