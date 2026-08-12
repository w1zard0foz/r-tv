#!/usr/bin/env python3
"""Build a curated M3U and an IPTV-org EPG channel-selection file."""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from pathlib import Path

COUNTRIES = {
    "us": "🇺🇸 United States", "uk": "🇬🇧 United Kingdom",
    "ca": "🇨🇦 Canada", "au": "🇦🇺 Australia", "nz": "🇳🇿 New Zealand",
    "ch": "🇨🇭 Switzerland", "ee": "🇪🇪 Estonia", "fi": "🇫🇮 Finland",
    "de": "🇩🇪 Germany", "fr": "🇫🇷 France", "it": "🇮🇹 Italy",
    "jp": "🇯🇵 Japan",
}
NEWS_NAMES = re.compile(
    r"\b(BBC News|CNN International|France ?24|DW (English|Deutsch)|"
    r"Al Jazeera English|Euronews|NHK World|Bloomberg|Sky News|TRT World|"
    r"CGTN|CNA)\b", re.I
)
ENTRY = re.compile(r'(?m)^#EXTINF:(?P<attrs>[^\r\n]*?),(?P<name>[^\r\n]+)\r?\n(?P<url>[^#\r\n][^\r\n]*)')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "curated-iptv-builder/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def load_json(url: str):
    return json.loads(fetch(url))


def parse_m3u(text: str):
    for match in ENTRY.finditer(text):
        attrs = dict(ATTR.findall(match.group("attrs")))
        yield attrs, match.group("name").strip(), match.group("url").strip()


def extinf(attrs, name, group):
    channel_id = attrs.get("tvg-id", "").split("@", 1)[0]
    fields = []
    if channel_id:
        fields.append(f'tvg-id="{channel_id}"')
    if attrs.get("tvg-logo"):
        fields.append(f'tvg-logo="{attrs["tvg-logo"]}"')
    fields.append(f'group-title="{group}"')
    return f'#EXTINF:-1 {" ".join(fields)},{name}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-iptv", type=Path, help="Use a local iptv-org/iptv checkout")
    parser.add_argument("--local-channels", type=Path, help="Use a local channels.json")
    parser.add_argument("--epg-sites", type=Path, help="Path to an iptv-org/epg sites directory")
    parser.add_argument("--output", type=Path, default=Path("playlist.m3u"))
    args = parser.parse_args()

    channels = (json.loads(args.local_channels.read_text()) if args.local_channels else
                load_json("https://iptv-org.github.io/api/channels.json"))
    meta = {x["id"]: x for x in channels}
    entries, selected_ids = [], set()

    def read_source(name):
        if args.local_iptv:
            return (args.local_iptv / "streams" / name).read_text(errors="replace")
        return fetch(f"https://raw.githubusercontent.com/iptv-org/iptv/master/streams/{name}").decode("utf-8", "replace")

    # Discover files from a local checkout or GitHub's directory API.
    if args.local_iptv:
        names = [p.name for p in (args.local_iptv / "streams").glob("*.m3u")]
    else:
        listing = load_json("https://api.github.com/repos/iptv-org/iptv/contents/streams")
        names = [x["name"] for x in listing if x["name"].endswith(".m3u")]

    seen_country = set()
    parsed_all = []
    for filename in sorted(names):
        code = filename.split("_", 1)[0].removesuffix(".m3u")
        wanted = code in COUNTRIES
        # Parse all sources to find a small, named set of international-news streams.
        if not wanted and not any(token in filename for token in ("news", "pluto", "samsung")):
            continue
        try:
            parsed = list(parse_m3u(read_source(filename)))
        except Exception as exc:
            print(f"warning: skipped {filename}: {exc}")
            continue
        parsed_all.extend(parsed)
        if wanted:
            for attrs, title, url in parsed:
                key = (attrs.get("tvg-id", "").split("@", 1)[0], url)
                if key in seen_country:
                    continue
                seen_country.add(key)
                entries.append((attrs, title, url, COUNTRIES[code]))
                if key[0]: selected_ids.add(key[0])

    # Topic groups deliberately duplicate a stream so Sparkle can browse it by topic.
    topic_seen = set()
    for attrs, title, url in parsed_all:
        cid = attrs.get("tvg-id", "").split("@", 1)[0]
        info = meta.get(cid, {})
        group = None
        if "star trek" in title.lower() or "startrek" in cid.lower():
            group = "🖖 Star Trek"
        elif "news" in info.get("categories", []) and NEWS_NAMES.search(title):
            group = "📰 International News"
        if group and (group, cid, url) not in topic_seen:
            topic_seen.add((group, cid, url))
            entries.append((attrs, title, url, group))
            if cid: selected_ids.add(cid)

    header = '#EXTM3U url-tvg="guide.xml"\n'
    body = "\n".join(f"{extinf(a, n, g)}\n{u}" for a, n, u, g in entries) + "\n"
    args.output.write_text(header + body, encoding="utf-8")

    # Select exact IPTV-org XMLTV definitions. Multiple sites may cover one channel;
    # prefer the first definition in sorted site order for predictable builds.
    if args.epg_sites:
        chosen = {}
        channel_re = re.compile(r"<channel\b[^>]*\bxmltv_id=\"([^\"]+)\"[^>]*>.*?</channel>")
        for path in sorted(args.epg_sites.glob("*/*.channels.xml")):
            for raw in channel_re.findall(path.read_text(errors="replace")):
                cid = html.unescape(raw).split("@", 1)[0]
                if cid in selected_ids and cid not in chosen:
                    # Recover the complete element containing this exact xmltv_id.
                    full = re.search(rf"<channel\b[^>]*\bxmltv_id=\"{re.escape(raw)}\"[^>]*>.*?</channel>", path.read_text(errors="replace"))
                    if full:
                        element = full.group(0)
                        element = re.sub(r'xmltv_id="[^"]+"', f'xmltv_id="{cid}"', element, count=1)
                        chosen[cid] = element
        Path("epg.channels.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<channels>\n' +
            "\n".join(chosen.values()) + "\n</channels>\n", encoding="utf-8")
        print(f"playlist entries={len(entries)}, unique IDs={len(selected_ids)}, EPG matches={len(chosen)}")
    else:
        print(f"playlist entries={len(entries)}, unique IDs={len(selected_ids)}")


if __name__ == "__main__":
    main()
