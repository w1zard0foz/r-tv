# Curated IPTV for Sparkle TV

This repository produces a playlist for the United States, United Kingdom,
Canada, Australia, New Zealand, Switzerland, Estonia, Finland, Germany, France,
Italy and Japan, plus International News and Star Trek topic groups.

The scheduled workflow refreshes the playlist daily from IPTV-org, matches EPG
channels by exact IPTV-org base ID, and creates a three-day combined XMLTV guide.
Streams are public links catalogued by IPTV-org and may be geo-blocked, temporary,
or unavailable. This project does not bypass subscriptions or geographic controls.

## Sparkle URLs

Replace `YOUR-USER` and `YOUR-REPO`:

* Playlist: `https://raw.githubusercontent.com/YOUR-USER/YOUR-REPO/main/playlist.m3u`
* EPG: `https://raw.githubusercontent.com/YOUR-USER/YOUR-REPO/main/guide.xml`

After uploading, open **Actions**, select **Refresh playlist and EPG**, choose
**Run workflow**, and wait for the green check before adding the EPG URL to Sparkle.
The first run can take a while because guide data is collected from several sites.

EPG coverage will not be 100%: some public streams have no published schedule, and
some guide sites can be temporarily unavailable. The workflow only replaces the
existing guide when the newly generated file contains programmes.
