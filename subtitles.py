#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Build a single WebVTT file from the segmented subtitle track of an HLS stream.

Kodi's built-in player ignores HLS subtitle renditions, so the segments are
downloaded and merged into one file that can be passed to ListItem.setSubtitles.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin


# Subtitle language to prefer for each addon region.
REGION_LANGUAGES = {
	"en": "en",
	"es": "es",
	"de": "de",
	"se": "sv",
	"eu": "en",
	"br": "pt",
	"lat": "es",
}

MAX_SEGMENTS = 2000
MAX_WORKERS = 8

_ATTRIBUTE_RE = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')
_TIMING_RE = re.compile(r'^\s*((?:\d+:)?\d{2}:\d{2}\.\d{3})\s+-->\s+((?:\d+:)?\d{2}:\d{2}\.\d{3})')


class SubtitleError(Exception):
	pass


def _attributes(line):
	attrs = {}
	for key, value in _ATTRIBUTE_RE.findall(line.split(":", 1)[1]):
		attrs[key] = value.strip('"')
	return attrs


def _language_matches(language, wanted):
	language = (language or "").lower()
	return language == wanted or language.startswith(wanted + "-")


def find_subtitle_playlist(master_text, master_url, region):
	"""Return (url, language) of the best subtitle rendition, or (None, None)."""
	renditions = []
	for line in master_text.splitlines():
		if line.startswith("#EXT-X-MEDIA:") and "TYPE=SUBTITLES" in line:
			attrs = _attributes(line)
			if attrs.get("URI"):
				renditions.append(attrs)
	if not renditions:
		return None, None

	wanted = REGION_LANGUAGES.get(region)
	chosen = None
	if wanted:
		chosen = next((r for r in renditions if _language_matches(r.get("LANGUAGE"), wanted)), None)
	if chosen is None:
		chosen = next((r for r in renditions if r.get("DEFAULT") == "YES"), renditions[0])
	return urljoin(master_url, chosen["URI"]), chosen.get("LANGUAGE") or wanted or "und"


def segment_urls(playlist_text, playlist_url):
	urls = [urljoin(playlist_url, line.strip()) for line in playlist_text.splitlines()
		if line.strip() and not line.startswith("#")]
	if len(urls) > MAX_SEGMENTS:
		raise SubtitleError("Too many subtitle segments: {}".format(len(urls)))
	return urls


def _seconds(timestamp):
	total = 0.0
	for part in timestamp.split(":"):
		total = total * 60 + float(part)
	return total


def merge_segments(bodies):
	"""Merge WebVTT segment bodies into one WebVTT document.

	Cues carry absolute stream timestamps, so they are kept as-is. Cues that
	span a segment boundary appear in both segments and are written once.
	"""
	cues = []
	seen = set()
	for body in bodies:
		body = body.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
		if "X-TIMESTAMP-MAP" in body:
			raise SubtitleError("Segments with X-TIMESTAMP-MAP are not supported")
		for block in body.split("\n\n"):
			lines = [line for line in block.split("\n") if line.strip()]
			index = next((i for i, line in enumerate(lines) if _TIMING_RE.match(line)), None)
			if index is None:
				# WEBVTT header, NOTE, STYLE or REGION block
				continue
			timing = lines[index].strip()
			text = "\n".join(lines[index + 1:])
			if not text or (timing, text) in seen:
				continue
			seen.add((timing, text))
			cues.append((_seconds(_TIMING_RE.match(timing).group(1)), timing, text))

	if not cues:
		raise SubtitleError("Subtitle track contains no cues")
	cues.sort(key=lambda cue: cue[0])
	return "WEBVTT\n\n" + "\n\n".join("{}\n{}".format(timing, text) for _, timing, text in cues) + "\n"


def build_subtitles(master_url, region, http_get):
	"""Return (vtt_text, language) for an HLS master playlist, or (None, None)
	when the stream has no subtitle track. http_get(url) must return text."""
	playlist_url, language = find_subtitle_playlist(http_get(master_url), master_url, region)
	if playlist_url is None:
		return None, None
	urls = segment_urls(http_get(playlist_url), playlist_url)
	with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
		bodies = list(executor.map(http_get, urls))
	return merge_segments(bodies), language
