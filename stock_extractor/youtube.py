"""
YouTube API and transcript fetcher with metadata support and fallback handling.
"""

import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

from stock_extractor.utils import parse_youtube_id

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
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                metadata["title"] = data.get("title", metadata["title"])
                metadata["channel"] = data.get("author_name", metadata["channel"])
                metadata["thumbnail_url"] = data.get("thumbnail_url", metadata["thumbnail_url"])
    except Exception as e:
        # Silently fall back to default metadata if offline or restricted
        pass
        
    return metadata

def fetch_transcript(
    video_id_or_url: str, 
    languages: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch raw transcript snippets and video metadata.
    
    Returns:
        (snippets, metadata) where snippets is a list of {'text', 'start', 'duration'}
    """
    video_id = parse_youtube_id(video_id_or_url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL or Video ID: '{video_id_or_url}'")
        
    metadata = fetch_video_metadata(video_id)
    
    if languages is None:
        languages = ['en', 'en-US', 'en-GB', 'hi', 'es', 'fr', 'de']
        
    raw_snippets = []
    
    # Try using YouTubeTranscriptApi with version fallback compatibility
    try:
        # Version >= 1.0 instantiated API
        api = YouTubeTranscriptApi()
        
        # Check if list method exists
        if hasattr(api, 'list'):
            t_list = api.list(video_id)
            # Find matching transcript or fallback to any available
            try:
                transcript_obj = t_list.find_transcript(languages)
            except Exception:
                try:
                    transcript_obj = t_list.find_generated_transcript(languages)
                except Exception:
                    # Pick first available transcript
                    available = list(t_list)
                    if available:
                        transcript_obj = available[0]
                    else:
                        raise NoTranscriptFound(video_id, languages, None)
                        
            # If transcript is in non-English and can be translated, attempt translation
            if transcript_obj.language_code not in ['en', 'en-US', 'en-GB'] and transcript_obj.is_translatable:
                try:
                    transcript_obj = transcript_obj.translate('en')
                except Exception:
                    pass
                    
            fetched = transcript_obj.fetch()
            if hasattr(fetched, 'to_raw_data'):
                raw_snippets = fetched.to_raw_data()
            elif isinstance(fetched, list):
                raw_snippets = fetched
            elif hasattr(fetched, 'snippets'):
                raw_snippets = [{'text': s.text, 'start': s.start, 'duration': s.duration} for s in fetched.snippets]
                
        elif hasattr(YouTubeTranscriptApi, 'get_transcript'):
            # Older static API version fallback
            raw_snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        raise RuntimeError(f"Could not retrieve transcript for video ID '{video_id}': {str(e)}")
    except Exception as e:
        # General exception handling
        raise RuntimeError(f"Error fetching transcript for '{video_id}': {str(e)}")

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
        
        # Group into blocks of ~1200 chars to minimize HTTP calls
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
