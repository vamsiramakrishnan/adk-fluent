"""
Live Translation Pipeline -- Streaming with .stream()

Real-world use case: Real-time translation pipeline for live event
transcription. Transcribes audio, translates, and formats subtitles --
all streaming. Critical for live conferences, court interpreting, and
broadcast captioning where latency matters.

In other frameworks: LangGraph supports streaming via astream_events but
requires graph compilation and manual event filtering. adk-fluent exposes
.stream() directly on any pipeline, making token-by-token output a single
async for loop.

Converted from cookbook example: 09_streaming.py

Usage:
    cd examples
    adk web streaming
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# The fluent API makes streaming a single async for loop:
# async for chunk in pipeline.stream("audio data here"):
#     print(chunk, end="")

transcriber = (
    Agent("transcriber")
    .model("gemini-2.5-flash")
    .instruct("Transcribe the incoming audio stream to text. Preserve speaker labels and timestamps.")
    .writes("transcript")
)

translator = (
    Agent("translator")
    .model("gemini-2.5-flash")
    .instruct("Translate the transcript to Spanish. Preserve speaker labels and formatting.")
)

pipeline_fluent = transcriber >> translator

# Build both to compare
built_native = pipeline_native
built_fluent = pipeline_fluent.build()

root_agent = built_fluent
