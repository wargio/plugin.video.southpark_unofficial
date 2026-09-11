#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Resolve public South Park episode pages to current playback manifests."""

import json
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit


REGION_DOMAINS = {
	"en": "https://southparkstudios.com",
	"es": "https://southparkstudios.com",
	"de": "https://www.southpark.de",
	"se": "https://www.southparkstudios.nu",
	"eu": "https://www.southparkstudios.com",
	"br": "https://www.southparkstudios.com.br",
	"lat": "https://www.southpark.lat",
}


class StreamResolutionError(Exception):
	pass


def _replace_query(url, query):
	parts = urlsplit(url)
	return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def build_episode_page_url(region, episode_url):
	domain = REGION_DOMAINS.get(region)
	if not domain or not isinstance(episode_url, str) or not episode_url:
		raise StreamResolutionError("Episode page is unavailable for this region")
	return urljoin(domain + "/", episode_url)


def _walk_dicts(value):
	if isinstance(value, dict):
		yield value
		for child in value.values():
			yield from _walk_dicts(child)
	elif isinstance(value, list):
		for child in value:
			yield from _walk_dicts(child)


def find_video_detail(data):
	"""Prefer Player.props.videoDetail, then current TVE redirect wrappers."""
	for node in _walk_dicts(data):
		if node.get("type") == "Player":
			detail = node.get("props", {}).get("videoDetail")
			if isinstance(detail, dict):
				return detail
	for node in _walk_dicts(data):
		detail = node.get("videoDetail")
		if isinstance(detail, dict):
			return detail
	return None


def extract_video_service_url(video_detail):
	if not isinstance(video_detail, dict):
		raise StreamResolutionError("Video details are missing")
	if video_detail.get("authRequired"):
		raise StreamResolutionError("This video requires authentication")
	mgid = video_detail.get("mgid")
	service_url = video_detail.get("videoServiceUrl")
	if not isinstance(mgid, str) or not mgid:
		raise StreamResolutionError("Video MGID is missing")
	if not _is_http_url(service_url):
		raise StreamResolutionError("This content is no longer available")
	return mgid, _replace_query(service_url, {})


def _is_http_url(url):
	if not isinstance(url, str):
		return False
	parts = urlsplit(url)
	return parts.scheme in ("http", "https") and bool(parts.netloc)


def extract_stitched_stream(data):
	stitched = data.get("stitchedstream") if isinstance(data, dict) else None
	if not isinstance(stitched, dict):
		raise StreamResolutionError("Stitched stream is unavailable")
	manifest_type = stitched.get("manifesttype")
	if isinstance(manifest_type, str):
		manifest_type = manifest_type.lower()
	if manifest_type not in ("hls", "dash"):
		raise StreamResolutionError("Unsupported stream manifest: {}".format(manifest_type))
	source = stitched.get("source")
	if not _is_http_url(source):
		raise StreamResolutionError("Playback manifest is unavailable")
	return manifest_type, source


def _fetch_json(http_get, url, description):
	try:
		data = http_get(url)
		if isinstance(data, bytes):
			data = data.decode("utf-8")
		if isinstance(data, str):
			data = json.loads(data)
		if not isinstance(data, dict):
			raise ValueError("JSON root is not an object")
		return data
	except StreamResolutionError:
		raise
	except Exception as error:
		raise StreamResolutionError("Unable to load {}: {}".format(description, error))


def resolve_episode_stream(region, episode_url, http_get):
	page_url = build_episode_page_url(region, episode_url)
	page_data = _fetch_json(http_get, _replace_query(page_url, {"json": "true"}), "episode JSON")
	video_detail = find_video_detail(page_data)
	mgid, service_url = extract_video_service_url(video_detail)
	service_data = _fetch_json(
		http_get,
		_replace_query(service_url, {"clientPlatform": "desktop"}),
		"video service JSON",
	)
	manifest_type, source = extract_stitched_stream(service_data)
	return {"mgid": mgid, "manifest_type": manifest_type, "source": source}
