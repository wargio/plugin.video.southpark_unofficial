import json
import unittest

from stream_resolver import (
	StreamResolutionError,
	build_episode_page_url,
	extract_stitched_stream,
	extract_video_service_url,
	find_video_detail,
	resolve_episode_stream,
)


FIXTURES = {
	"page_player.json": '{"children":[{"type":"MainContainer","children":[{"type":"AviaWrapper","children":[{"type":"FlexWrapper","children":[{"type":"AuthSuiteWrapper","children":[{"type":"Player","props":{"videoDetail":{"mgid":"mgid:arc:episode:test:123","authRequired":false,"videoServiceUrl":"https://media.example.test/video?device=old"}}}]}]}]}]}]}',
	"page_fallback.json": '{"children":[{"handleTVEAuthRedirection":{"videoDetail":{"mgid":"mgid:arc:episode:test:456","authRequired":false,"videoServiceUrl":"https://media.example.test/fallback?foo=bar"}}}]}',
	"page_unavailable.json": '{"children":[{"type":"Player","props":{"videoDetail":{"mgid":"mgid:arc:episode:test:missing","authRequired":false,"videoServiceUrl":null}}}]}',
	"service_hls.json": '{"stitchedstream":{"manifesttype":"hls","source":"https://cdn.example.test/master.m3u8"}}',
	"service_dash.json": '{"stitchedstream":{"manifesttype":"dash","source":"https://cdn.example.test/manifest.mpd"}}',
	"malformed.json": '{"children": [this is not valid JSON]',
}


def fixture(name, raw=False):
	text = FIXTURES[name]
	return text if raw else json.loads(text)


class FakeHTTP:
	def __init__(self, responses):
		self.responses = responses
		self.calls = []

	def __call__(self, url):
		self.calls.append(url)
		return self.responses[url]


class StreamResolverTests(unittest.TestCase):
	def test_locates_player_video_detail_through_wrappers(self):
		detail = find_video_detail(fixture("page_player.json"))
		self.assertEqual(detail["mgid"], "mgid:arc:episode:test:123")

	def test_locates_fallback_video_detail(self):
		detail = find_video_detail(fixture("page_fallback.json"))
		self.assertEqual(detail["mgid"], "mgid:arc:episode:test:456")

	def test_extracts_and_cleans_video_service_url(self):
		mgid, url = extract_video_service_url(find_video_detail(fixture("page_player.json")))
		self.assertEqual(mgid, "mgid:arc:episode:test:123")
		self.assertEqual(url, "https://media.example.test/video")

	def test_extracts_hls_stitched_stream(self):
		self.assertEqual(
			extract_stitched_stream(fixture("service_hls.json")),
			("hls", "https://cdn.example.test/master.m3u8"),
		)

	def test_extracts_dash_stitched_stream(self):
		self.assertEqual(
			extract_stitched_stream(fixture("service_dash.json")),
			("dash", "https://cdn.example.test/manifest.mpd"),
		)

	def test_missing_video_is_reported(self):
		with self.assertRaisesRegex(StreamResolutionError, "no longer available"):
			extract_video_service_url(find_video_detail(fixture("page_unavailable.json")))

	def test_malformed_json_is_reported(self):
		http = lambda url: fixture("malformed.json", raw=True)
		with self.assertRaisesRegex(StreamResolutionError, "episode JSON"):
			resolve_episode_stream("de", "/folgen/test", http)

	def test_de_path_and_network_requests(self):
		page_url = "https://www.southpark.de/folgen/test?json=true"
		service_url = "https://media.example.test/video?clientPlatform=desktop"
		http = FakeHTTP({
			page_url: fixture("page_player.json"),
			service_url: fixture("service_hls.json"),
		})
		stream = resolve_episode_stream("de", "/folgen/test", http)
		self.assertEqual(stream["manifest_type"], "hls")
		self.assertEqual(http.calls, [page_url, service_url])

	def test_eu_path_and_network_requests(self):
		page_url = "https://www.southparkstudios.com/episodes/test?json=true"
		service_url = "https://media.example.test/fallback?clientPlatform=desktop"
		http = FakeHTTP({
			page_url: fixture("page_fallback.json"),
			service_url: fixture("service_dash.json"),
		})
		stream = resolve_episode_stream("eu", "/episodes/test", http)
		self.assertEqual(stream["manifest_type"], "dash")
		self.assertEqual(http.calls, [page_url, service_url])

	def test_region_page_urls(self):
		self.assertEqual(build_episode_page_url("de", "/folgen/x"), "https://www.southpark.de/folgen/x")
		self.assertEqual(build_episode_page_url("eu", "/episodes/x"), "https://www.southparkstudios.com/episodes/x")


if __name__ == "__main__":
	unittest.main()
