"""
YouTube API and transcript fetcher with metadata support, cookie authentication, proxy routing,
and Invidious mirror fallback to overcome Cloud Datacenter IP blocking.
"""

import os
import json
import tempfile
import urllib.request
import urllib.error
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from youtube_transcript_api import (
    YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
)

try:
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig, ProxyConfig
except ImportError:
    GenericProxyConfig = None
    WebshareProxyConfig = None
    ProxyConfig = None

from stock_extractor.utils import parse_youtube_id

# Public Invidious mirror instances for cloud fallback
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.io.lol",
    "https://vid.priv.au",
    "https://yewtu.be"
]


def get_cookie_file_path() -> Optional[str]:
    """
    Check for YouTube cookies configured via file path or raw text environment variable.
    Allows authenticated sessions in cloud environments (Render / Leapcell).
    """
    cookie_file = os.getenv("YOUTUBE_COOKIES_FILE")
    if cookie_file and os.path.exists(cookie_file):
        return cookie_file

    cookie_text = os.getenv("YOUTUBE_COOKIES_TEXT")
    if cookie_text and cookie_text.strip():
        # Write to a persistent temp file
        tmp_dir = tempfile.gettempdir()
        target = os.path.join(tmp_dir, "youtube_cookies.txt")
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(cookie_text.strip())
            return target
        except Exception:
            pass

    return None


def get_proxy_url() -> Optional[str]:
    """Get raw proxy URL string from environment if defined."""
    return os.getenv("PROXY_URL") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")


def get_proxy_config() -> Optional[Any]:
    """
    Build a YouTubeTranscriptApi ProxyConfig for requests.
    Uses GenericProxyConfig to maintain consistent connection and session IP affinity
    between the watch page and timedtext caption requests (preventing 429 errors caused
    by rotating proxies switching IPs mid-stream).
    """
    ws_user = os.getenv("WEBSHARE_USERNAME")
    ws_pass = os.getenv("WEBSHARE_PASSWORD")
    proxy_url = get_proxy_url()

    if not proxy_url and ws_user and ws_pass:
        proxy_url = f"http://{ws_user.strip()}:{ws_pass.strip()}@p.webshare.io:80"

    if not proxy_url or not proxy_url.strip():
        return None

    proxy_url = proxy_url.strip()

    if GenericProxyConfig is not None:
        # GenericProxyConfig preserves connection keep-alive and avoids forced mid-stream IP rotation
        return GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)

    return {"http": proxy_url, "https": proxy_url}


def fetch_video_metadata(video_id: str) -> Dict[str, Any]:
    """
    Fetch YouTube video metadata (Title, Author/Channel, Thumbnail) using YouTube oEmbed.
    Does not require any YouTube API key.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"

    metadata = {
        "video_id": video_id,
        "video_url": video_url,
        "title": f"YouTube Video ({video_id})",
        "channel": "Unknown Channel",
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    }

    try:
        req = urllib.request.Request(
            oembed_url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                metadata["title"] = data.get("title", metadata["title"])
                metadata["channel"] = data.get("author_name", metadata["channel"])
                metadata["thumbnail_url"] = data.get("thumbnail_url", metadata["thumbnail_url"])
    except Exception:
        pass

    return metadata


def fetch_transcript_via_invidious(video_id: str, languages: List[str]) -> Optional[List[Dict[str, Any]]]:
    """
    Fallback method: Query public Invidious API instances to fetch captions.
    Runs on independent residential networks to bypass YouTube datacenter IP blocking.
    """
    proxy_url = get_proxy_url()
    opener = None
    if proxy_url:
        try:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            opener = urllib.request.build_opener(proxy_handler)
        except Exception:
            opener = None

    def _make_request(url: str, headers: Dict[str, str], timeout: int = 10):
        req = urllib.request.Request(url, headers=headers)
        if opener:
            return opener.open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout)

    for base_url in INVIDIOUS_INSTANCES:
        try:
            api_url = f"{base_url}/api/v1/captions/{video_id}"
            with _make_request(api_url, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=8) as resp:
                if resp.status == 200:
                    captions = json.loads(resp.read().decode('utf-8'))
                    if not captions or not isinstance(captions, list):
                        continue

                    # Find matching caption track
                    selected_caption = None
                    for lang in languages:
                        for cap in captions:
                            if cap.get("language_code") == lang:
                                selected_caption = cap
                                break
                        if selected_caption:
                            break

                    if not selected_caption and captions:
                        selected_caption = captions[0]

                    if selected_caption and "url" in selected_caption:
                        cap_url = selected_caption["url"]
                        if cap_url.startswith("/"):
                            cap_url = f"{base_url}{cap_url}"

                        # Fetch subtitle content (VTT format)
                        with _make_request(cap_url, {"User-Agent": "Mozilla/5.0"}, timeout=10) as vtt_resp:
                            vtt_text = vtt_resp.read().decode('utf-8', errors='replace')
                            snippets = parse_vtt_to_snippets(vtt_text)
                            if snippets:
                                return snippets
        except Exception:
            continue

    return None


def parse_vtt_to_snippets(vtt_text: str) -> List[Dict[str, Any]]:
    """Parse WebVTT subtitle text into standard snippet dicts {'text', 'start', 'duration'}."""
    import re
    snippets = []
    lines = vtt_text.splitlines()
    time_pattern = re.compile(r'(\d{2}:)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}:)?(\d{2}):(\d{2})\.(\d{3})')

    current_start = 0.0
    current_duration = 3.0
    current_text = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("WEBVTT") or "-->" not in line_clean and not current_text:
            match = time_pattern.search(line_clean)
            if match:
                if current_text:
                    snippets.append({
                        "text": " ".join(current_text),
                        "start": current_start,
                        "duration": current_duration
                    })
                    current_text = []

                # Parse start time
                h1 = int(match.group(1).replace(":", "")) if match.group(1) else 0
                m1 = int(match.group(2))
                s1 = int(match.group(3))
                ms1 = int(match.group(4))
                current_start = float(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0)

                h2 = int(match.group(5).replace(":", "")) if match.group(5) else 0
                m2 = int(match.group(6))
                s2 = int(match.group(7))
                ms2 = int(match.group(8))
                end_time = float(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0)
                current_duration = max(0.5, end_time - current_start)
            continue

        match = time_pattern.search(line_clean)
        if match:
            if current_text:
                snippets.append({
                    "text": " ".join(current_text),
                    "start": current_start,
                    "duration": current_duration
                })
                current_text = []
            h1 = int(match.group(1).replace(":", "")) if match.group(1) else 0
            m1 = int(match.group(2))
            s1 = int(match.group(3))
            ms1 = int(match.group(4))
            current_start = float(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0)

            h2 = int(match.group(5).replace(":", "")) if match.group(5) else 0
            m2 = int(match.group(6))
            s2 = int(match.group(7))
            ms2 = int(match.group(8))
            end_time = float(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0)
            current_duration = max(0.5, end_time - current_start)
        else:
            # Subtitle text line
            clean_line = re.sub(r'<[^>]+>', '', line_clean)  # Strip HTML/VTT tags
            if clean_line:
                current_text.append(clean_line)

    if current_text:
        snippets.append({
            "text": " ".join(current_text),
            "start": current_start,
            "duration": current_duration
        })

    return snippets


def fetch_transcript(
    video_id_or_url: str, 
    languages: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch raw transcript snippets and video metadata with multi-tier anti-blocking defenses:
    Tier 1: Standard YouTubeTranscriptApi with Cookies & Proxy support
    Tier 2: Invidious Open-Source Mirror Fallback
    """
    video_id = parse_youtube_id(video_id_or_url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: '{video_id_or_url}'")

    metadata = fetch_video_metadata(video_id)

    if languages is None:
        languages = ['en', 'en-US', 'en-GB', 'hi', 'es', 'fr', 'de']

def _create_browser_session(cookie_file: Optional[str] = None):
    """Create a requests.Session with realistic desktop browser headers and optional cookies."""
    import requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Referer": "https://www.youtube.com/"
    })
    if cookie_file:
        try:
            import http.cookiejar
            jar = http.cookiejar.MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies = jar
        except Exception as e:
            pass
    return session


def _attempt_fetch_with_api(api: YouTubeTranscriptApi, video_id: str, languages: List[str], cookie_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """Attempt transcript extraction using YouTubeTranscriptApi (v1.x list/fetch or legacy)."""
    if hasattr(api, 'list'):
        t_list = api.list(video_id)
        try:
            transcript_obj = t_list.find_transcript(languages)
        except Exception:
            try:
                transcript_obj = t_list.find_generated_transcript(languages)
            except Exception:
                available = list(t_list)
                if available:
                    transcript_obj = available[0]
                else:
                    raise NoTranscriptFound(video_id, languages, None)

        # Translate to English if needed and translatable
        if transcript_obj.language_code not in ['en', 'en-US', 'en-GB'] and transcript_obj.is_translatable:
            try:
                transcript_obj = transcript_obj.translate('en')
            except Exception:
                pass

        fetched = transcript_obj.fetch()
        if hasattr(fetched, 'to_raw_data'):
            return fetched.to_raw_data()
        elif isinstance(fetched, list):
            return fetched
        elif hasattr(fetched, 'snippets'):
            return [{'text': s.text, 'start': s.start, 'duration': s.duration} for s in fetched.snippets]
        return list(fetched)

    elif hasattr(YouTubeTranscriptApi, 'get_transcript'):
        kwargs = {}
        if cookie_file:
            kwargs["cookies"] = cookie_file
        proxy_url = get_proxy_url()
        if proxy_url:
            kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}
        return YouTubeTranscriptApi.get_transcript(video_id, languages=languages, **kwargs)
    else:
        raise RuntimeError("Installed youtube_transcript_api package has neither 'list' nor 'get_transcript'.")


def fetch_transcript(
    video_id_or_url: str, 
    languages: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch raw transcript snippets and video metadata with multi-tier anti-blocking defenses:
    Tier 1A: Proxy-routed YouTubeTranscriptApi (if configured in environment)
    Tier 1B: Direct YouTubeTranscriptApi (automatic fallback if proxy encounters 429/block)
    Tier 2: Invidious Open-Source Mirror Fallback (residential mirrors)
    """
    video_id = parse_youtube_id(video_id_or_url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: '{video_id_or_url}'")

    metadata = fetch_video_metadata(video_id)

    if languages is None:
        languages = ['en', 'en-US', 'en-GB', 'hi', 'es', 'fr', 'de']

    raw_snippets = []
    cookie_file = get_cookie_file_path()
    proxy_config = get_proxy_config()
    last_error = None

    # -------------------------------------------------------------
    # Tier 1A: Proxy Attempt (if proxy_config configured)
    # -------------------------------------------------------------
    if proxy_config:
        try:
            session_proxy = _create_browser_session(cookie_file=cookie_file)
            if hasattr(proxy_config, 'to_requests_dict'):
                api = YouTubeTranscriptApi(proxy_config=proxy_config, http_client=session_proxy)
            elif isinstance(proxy_config, dict):
                session_proxy.proxies.update(proxy_config)
                api = YouTubeTranscriptApi(http_client=session_proxy)
            else:
                api = YouTubeTranscriptApi(http_client=session_proxy)

            raw_snippets = _attempt_fetch_with_api(api, video_id, languages, cookie_file=cookie_file)
        except Exception as proxy_err:
            last_error = proxy_err
            # If proxy encounters 429 rate limits, connection errors, or timeouts, fall back to direct!
            pass

    # -------------------------------------------------------------
    # Tier 1B: Direct Connection Attempt (if no proxy OR if proxy was blocked/429)
    # -------------------------------------------------------------
    if not raw_snippets:
        try:
            session_direct = _create_browser_session(cookie_file=cookie_file)
            api_direct = YouTubeTranscriptApi(http_client=session_direct)
            raw_snippets = _attempt_fetch_with_api(api_direct, video_id, languages, cookie_file=cookie_file)
        except Exception as direct_err:
            last_error = last_error or direct_err

    # -------------------------------------------------------------
    # Tier 2: Invidious Mirror API Fallback
    # -------------------------------------------------------------
    if not raw_snippets:
        invidious_snippets = fetch_transcript_via_invidious(video_id, languages)
        if invidious_snippets:
            raw_snippets = invidious_snippets
        else:
            raise RuntimeError(
                f"Could not retrieve transcript for video '{video_id}'. "
                f"YouTube error: {last_error}. (Tip: Add YOUTUBE_COOKIES_TEXT or PROXY_URL if running in a cloud datacenter)"
            )

    # Clean raw snippets
    cleaned_snippets = []
    for item in raw_snippets:
        if isinstance(item, dict):
            text = item.get('text', '')
            start = float(item.get('start', 0.0))
            duration = float(item.get('duration', 0.0))
        else:
            text = getattr(item, 'text', '')
            start = float(getattr(item, 'start', 0.0))
            duration = float(getattr(item, 'duration', 0.0))

        cleaned_snippets.append({
            'text': text,
            'start': start,
            'duration': duration
        })

    cleaned_snippets = translate_snippets_if_needed(cleaned_snippets)
    return cleaned_snippets, metadata


def translate_snippets_if_needed(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Translate non-English transcript snippets to English using free DeepTranslator if non-ASCII detected."""
    if not snippets:
        return snippets

    sample_text = " ".join([s.get('text', '') for s in snippets[:30]])
    non_ascii_count = sum(1 for c in sample_text if ord(c) > 127)

    if non_ascii_count < 15:
        return snippets

    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')

        chunk_text = ""
        chunk_snippets = []
        translated_snippets = []

        for s in snippets:
            txt = s.get('text', '')
            if len(chunk_text) + len(txt) > 1200 and chunk_text:
                try:
                    en_txt = translator.translate(chunk_text)
                    if "Error 500" in en_txt or "Server Error" in en_txt or "That’s an error" in en_txt:
                        en_txt = chunk_text
                except Exception:
                    en_txt = chunk_text

                words = en_txt.split()
                n_snips = len(chunk_snippets)
                words_per_snip = max(1, len(words) // n_snips)

                for i, snip in enumerate(chunk_snippets):
                    sub = words[i*words_per_snip : (i+1)*words_per_snip] if i < n_snips - 1 else words[i*words_per_snip:]
                    translated_snippets.append({
                        'text': " ".join(sub) if sub else snip['text'],
                        'start': snip['start'],
                        'duration': snip['duration']
                    })
                chunk_text = txt
                chunk_snippets = [s]
            else:
                chunk_text += " " + txt if chunk_text else txt
                chunk_snippets.append(s)

        if chunk_snippets:
            try:
                en_txt = translator.translate(chunk_text)
                if "Error 500" in en_txt or "Server Error" in en_txt or "That’s an error" in en_txt:
                    en_txt = chunk_text
            except Exception:
                en_txt = chunk_text
            words = en_txt.split()
            n_snips = len(chunk_snippets)
            words_per_snip = max(1, len(words) // n_snips)
            for i, snip in enumerate(chunk_snippets):
                sub = words[i*words_per_snip : (i+1)*words_per_snip] if i < n_snips - 1 else words[i*words_per_snip:]
                translated_snippets.append({
                    'text': " ".join(sub) if sub else snip['text'],
                    'start': snip['start'],
                    'duration': snip['duration']
                })

        return translated_snippets
    except Exception:
        return snippets
