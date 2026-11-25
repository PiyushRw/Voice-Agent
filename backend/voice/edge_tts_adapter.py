"""EdgeTTS adapter – corrected for livekit-agents 1.8.x.

AudioEmitter.initialize() now takes:
  request_id, sample_rate, num_channels, mime_type, frame_size_ms (optional)

The _run override receives an AudioEmitter instance directly.
"""
import asyncio
import os
import re

import edge_tts
from livekit.agents import tts, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS


class EdgeTTS(tts.TTS):
    def __init__(self):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1,
        )

    def synthesize(self, text, *, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return _EdgeSpeech(tts=self, input_text=text, conn_options=conn_options)


class _EdgeSpeech(tts.ChunkedStream):
    """
    ChunkedStream subclass for EdgeTTS.

    In livekit-agents 1.8 the _run method receives an AudioEmitter.
    Call output_emitter.initialize() once, then push() raw MP3 bytes,
    then flush() to signal the end of the segment.
    """

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        hindi = re.search(r"[\u0900-\u097f]", self._input_text)
        voice = (
            (os.getenv("EDGE_TTS_HINDI_VOICE") or "hi-IN-SwaraNeural")
            if hindi
            else (os.getenv("EDGE_TTS_ENGLISH_VOICE") or "en-IN-NeerjaNeural")
        )

        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=24000,
            num_channels=1,
            mime_type="audio/mpeg",    # edge_tts streams MP3 frames
        )

        async with asyncio.timeout(30):
            async for packet in edge_tts.Communicate(self._input_text, voice).stream():
                if packet["type"] == "audio":
                    output_emitter.push(packet["data"])

        output_emitter.flush()
