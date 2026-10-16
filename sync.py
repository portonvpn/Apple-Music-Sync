import os
import re
import json
import urllib.request
import subprocess

PLAYLIST_URL = os.environ.get("APPLE_MUSIC_PLAYLIST_URL", "")
LOCAL_DIR = "music_library"
os.makedirs(LOCAL_DIR, exist_ok=True)

if not PLAYLIST_URL:
    print("Error: APPLE_MUSIC_PLAYLIST_URL is missing.")
    exit(1)

print(f"Scraping playlist: {PLAYLIST_URL}")
req = urllib.request.Request(
    PLAYLIST_URL,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
)

try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")
except Exception as e:
    print(f"Failed to fetch Apple Music webpage: {e}")
    exit(1)

target_songs = []

# Method 1: Parse serialized-server-data
data_blocks = re.findall(r'<script[^>]*id=["\']serialized-server-data["\'][^>]*>(.*?)</script>', html, re.DOTALL)
for block in data_blocks:
    try:
        parsed = json.loads(block.strip())
        if isinstance(parsed, list):
            for entry in parsed:
                data = entry.get("data", {})
                sections = data.get("sections", [])
                for sec in sections:
                    for item in sec.get("items", []):
                        title = item.get("title")
                        artist = item.get("artistName")
                        if title and artist:
                            target_songs.append({"artist": artist, "title": title})
    except Exception:
        pass

# Method 2: Inspect application/json scripts
if not target_songs:
    script_tags = re.findall(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    for tag in script_tags:
        if '"artistName"' in tag and '"title"' in tag:
            try:
                blob = json.loads(tag.strip())
                def walk(obj):
                    if isinstance(obj, dict):
                        if "title" in obj and "artistName" in obj:
                            t = obj.get("title")
                            a = obj.get("artistName")
                            if isinstance(t, str) and isinstance(a, str):
                                target_songs.append({"artist": a, "title": t})
                        for v in obj.values():
                            walk(v)
                    elif isinstance(obj, list):
                        for el in obj:
                            walk(el)
                walk(blob)
            except Exception:
                pass

# Method 3: Regex fallback
if not target_songs:
    matches = re.findall(r'\"(?:title|name)\":\"([^\"]+)\"[^\{\}\[\]]*?\"artistName\":\"([^\"]+)\"', html)
    for title, artist in matches:
        target_songs.append({"artist": artist, "title": title})

unique_songs = []
seen = set()
for s in target_songs:
    key = f"{s['artist']} - {s['title']}".lower()
    if key not in seen:
        seen.add(key)
        unique_songs.append(s)

print(f"Detected {len(unique_songs)} songs in playlist.")

def sanitize(val):
    return re.sub(r'[\\/*?:"<>|]', "", val).strip()

# --- TEST MODE: PROCESS EXACTLY ONE SONG ---
downloaded_count = 0

for song in unique_songs:
    if downloaded_count >= 1:
        print("\n[TEST MODE] Reached 1 song limit. Stopping download loop.")
        break

    artist = song["artist"]
    title = song["title"]
    base_name = f"{sanitize(artist)} - {sanitize(title)}" if artist else sanitize(title)
    expected_filename = f"{base_name}.m4a"
    file_path = os.path.join(LOCAL_DIR, expected_filename)

    if os.path.exists(file_path):
        print(f"Skipping already existing: {expected_filename}")
        continue

    print(f"\n---> [TEST] Attempting fetch for 1 song: {artist} - {title}")

    # Primary: YouTube Music with mobile client spoofing
    yt_query = f"ytsearch1:{artist} {title} audio"
    cmd_yt = [
        "yt-dlp",
        yt_query,
        "-x",
        "--audio-format", "m4a",
        "--embed-metadata",
        "--extractor-args", "youtube:player_client=android",
        "-o", file_path
    ]
    res = subprocess.run(cmd_yt)

    # Secondary Fallback: SoundCloud if YouTube blocks runner IP
    if res.returncode != 0 or not os.path.exists(file_path):
        print(f"YouTube attempt blocked. Trying SoundCloud fallback for: {artist} - {title}")
        sc_query = f"scsearch1:{artist} {title}"
        cmd_sc = [
            "yt-dlp",
            sc_query,
            "-x",
            "--audio-format", "m4a",
            "--embed-metadata",
            "-o", file_path
        ]
        res = subprocess.run(cmd_sc)

    if os.path.exists(file_path):
        print(f"Successfully downloaded 1 test song: {file_path}")
        downloaded_count += 1
    else:
        print(f"Failed to fetch test song: {artist} - {title}")

print("\nTest sync script execution finished.")
