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
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
)
html = urllib.request.urlopen(req).read().decode("utf-8")

target_songs = []
scripts = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)

for raw_json in scripts:
    try:
        data = json.loads(raw_json.strip())
        items = data.get("track", []) or data.get("itemListElement", [])
        for item in items:
            song_obj = item.get("item", item)
            name = song_obj.get("name", "").strip()
            artist = ""
            by_artist = song_obj.get("byArtist", [])
            if isinstance(by_artist, list) and by_artist:
                artist = by_artist[0].get("name", "").strip()
            elif isinstance(by_artist, dict):
                artist = by_artist.get("name", "").strip()
            if name:
                target_songs.append({"artist": artist, "title": name})
    except Exception:
        continue

if not target_songs:
    matches = re.findall(r'"songName":"([^"]+)".*?"artistName":"([^"]+)"', html)
    for title, artist in matches:
        target_songs.append({"artist": artist, "title": title})

print(f"Detected {len(target_songs)} songs in playlist.")

def sanitize(val):
    return re.sub(r'[\\/*?:"<>|]', "", val).strip()

expected_filenames = set()

for song in target_songs:
    artist = song["artist"]
    title = song["title"]
    base_name = f"{sanitize(artist)} - {sanitize(title)}" if artist else sanitize(title)
    expected_filename = f"{base_name}.m4a"
    expected_filenames.add(expected_filename)

    file_path = os.path.join(LOCAL_DIR, expected_filename)
    if os.path.exists(file_path):
        continue

    query = f"ytsearch1:{artist} {title} official audio"
    print(f"Fetching: {artist} - {title}")
    
    cmd = [
        "yt-dlp",
        query,
        "-x",
        "--audio-format", "m4a",
        "--embed-metadata",
        "--embed-thumbnail",
        "-o", file_path
    ]
    subprocess.run(cmd)

for fname in os.listdir(LOCAL_DIR):
    if fname.endswith(".m4a") and fname not in expected_filenames:
        print(f"Deleting removed song: {fname}")
        os.remove(os.path.join(LOCAL_DIR, fname))

print("Sync completed.")
