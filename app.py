from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import openai
import json
import os
import re
from google import genai
from google.genai import types
import azure.cognitiveservices.speech as speechsdk

app = Flask(__name__)

# Enable CORS for all routes, allowing requests from your frontend
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
system_instruction_split_context="""# Improved Prompt

                                    You are an AI assistant tasked with segmenting a script into distinct scenes and defining a visual style for image generation. These segments will be used to create individual images that, when combined, form a seamless video. Your goal is to ensure each segment captures a unique, visually compelling moment while maintaining the narrative’s flow and coherence.

                                    ## Objectives

                                    1. **Segment the Script:**
                                    - Divide the script into distinct scenes or contexts based on clear shifts in setting, characters, tone, narrative focus, or significant actions.
                                    - Aim for frequent segmentation to capture subtle changes, ensuring each segment is a standalone visual unit suitable for generating a unique image that contributes to the video’s progression.

                                    2. **Determine the Visual Style:**
                                    - **Global Style:** Analyze the script’s overall theme, tone, and genre to select a detailed visual style (e.g., "hyper-realistic with muted tones and harsh lighting") that ensures consistency across all images.
                                    - **Segment-Specific Style (Optional):** Provide a style modifier for any segment where the mood or context significantly deviates from the global style (e.g., a flashback or intense emotion), enhancing its visual distinction.

                                    ## Task

                                    - **Segment the Script:**
                                    - Identify natural breaks in the script where a new scene begins, using the guidelines below.
                                    - Ensure each segment is granular enough to represent a distinct visual moment but cohesive enough to maintain narrative continuity when sequenced.
                                    - **Define the Visual Style:**
                                    - **Global Style:** Choose a detailed, descriptive style based on the entire script’s content to guide consistent image generation.
                                    - **Segment-Specific Style:** Add a modifier only when necessary to highlight a segment’s unique atmosphere or context.
                                    - **Output as JSON:**
                                    - Produce a structured JSON object containing the segmented script and visual style details.

                                    ## Input

                                    - A single string containing the full script.

                                    ## Output

                                    - A valid JSON object with:
                                    - **`"segments"`: An array of objects, each containing:**
                                    - **`"text"`: A string of the segment’s text, representing a distinct scene.**
                                    - **`"style_modifier"`: An optional string (e.g., "sepia-toned") for segment-specific tweaks. Omit if not applicable.**
                                    - **`"script_scene_style"`: A string specifying the detailed global visual style (e.g., "gothic with dark shadows and crimson accents") applied to all segments unless modified.**

                                    ## Guidelines for Identifying Scene Changes

                                    - **Segment the script at points of noticeable change, prioritizing visual distinction for video sequencing:**
                                    - **Location or Setting:** A shift from one place to another (e.g., indoors to outdoors, diner to street).
                                    - **Characters:** Introduction, exit, or shift in focus of characters (e.g., a new person enters, or the perspective changes).
                                    - **Time:** Transitions across time (e.g., evening to midnight, or a leap to the next day).
                                    - **Tone or Mood:** A change in emotional atmosphere (e.g., calm to tense, routine to mysterious).
                                    - **Significant Actions or Events:** Key moments like locking a door, finding an object, or a dramatic gesture.
                                    - **Narrative Focus:** Shifts in storytelling emphasis (e.g., from a character’s routine to an investigation).
                                    - **New Plot Elements:** Introduction of critical details (e.g., a witness’s testimony or a clue).
                                    - **For dialogue-heavy scenes:**
                                    - Segment based on changes in speaker, tone, or significant actions/reactions if they suggest distinct visuals (e.g., a character standing up mid-conversation).
                                    - Group rapid exchanges into a single segment if they occur in the same context without visual shifts, but split if actions or reactions warrant separate images.

                                    ## Guidelines for Determining Visual Style

                                    - **Global Style:**
                                    - Analyze the script holistically to determine its overarching theme, tone, or genre.
                                    - Select a detailed style with:
                                    - **Base Style:** E.g., "hyper-realistic," "cartoonish," "gothic."
                                    - **Descriptive Qualifiers:** E.g., "with muted tones and harsh lighting," "with vibrant colors and soft edges."
                                    - Examples:
                                    - Crime/Mystery: "hyper-realistic with muted tones and harsh lighting."
                                    - Horror: "gothic with dark shadows and crimson accents."
                                    - Comedy: "cartoonish with bold outlines and bright colors."
                                    - Ensure the description is keyword-rich and specific to guide consistent image generation.
                                    - **Segment-Specific Style (Optional):**
                                    - Use concise modifiers (e.g., "dreamy haze," "high contrast with deep shadows") only when a segment’s context significantly differs from the global style.
                                    - Examples:
                                    - Flashback: "sepia-toned with soft focus."
                                    - Dream Sequence: "surreal with glowing edges."
                                    - Suspenseful Moment: "high contrast with distorted shadows."
                                    - Modifiers should refine, not replace, the global style.

                                    ## Additional Instructions

                                    - **Segment Text:**
                                    - Each `"text"` should be a complete narrative or visual unit (typically 1-3 sentences), but split more frequently for subtle shifts to ensure visual variety.
                                    - If a sentence bridges scenes, place it in the segment where its primary action or change occurs.
                                    - Preserve original punctuation and sentence structure.
                                    - **Balance Segmentation:**
                                    - Avoid over-segmenting into incomplete fragments (e.g., single phrases) or under-segmenting by merging unrelated moments.
                                    - Ensure each segment can standalone visually while contributing to the video’s narrative flow.
                                    - **Visual Style Application:**
                                    - Base the global style on the entire script for consistency, with modifiers adding flexibility for standout moments.
                                    - Use modifiers sparingly, reserving them for significant deviations like flashbacks, dreams, or emotional peaks.
                                    - **Video Consideration:**
                                    - List segments in their original order to maintain chronological sequence.
                                    - Ensure transitions between segments feel natural when viewed as a video, capturing the script’s progression.
                                    - **JSON Formatting:**
                                    - Use proper syntax (double quotes for keys and strings) and omit `"style_modifier"` if not needed.

                                    ## Example 1

                                    **Input:**

                                    "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids. At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away. She never made it home. The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat. But Linda was gone. The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street. She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument. With no signs of struggle and no immediate suspects, the case went cold."

                                    **Output:**

                                    ```json
                                    {
                                    "segments": [
                                    {
                                    "text": "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids."
                                    },
                                    {
                                    "text": "At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away."
                                    },
                                    {
                                    "text": "She never made it home."
                                    },
                                    {
                                    "text": "The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat."
                                    },
                                    {
                                    "text": "But Linda was gone."
                                    },
                                    {
                                    "text": "The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street."
                                    },
                                    {
                                    "text": "She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument.",
                                    "style_modifier": "eerie atmosphere with distorted shadows"
                                    },
                                    {
                                    "text": "With no signs of struggle and no immediate suspects, the case went cold."
                                    }
                                    ],
                                    "script_scene_style": "hyper-realistic with muted tones and harsh lighting"
                                    }
                                    **Explanation:**

                                    - Segmentation: Eight segments capture key visual moments (e.g., Linda at the diner, her car abandoned, the scream), ensuring each can produce a distinct image that flows logically in a video.
                                    - Global Style: "hyper-realistic with muted tones and harsh lighting" reflects the gritty crime/mystery tone, detailed enough for consistent image generation.
                                    - Modifier: Added to the scream segment to emphasize its eerie mood, enhancing its visual impact.

                                    ## Example 2

                                    **Input:**

                                    "The old house creaked as the wind howled outside. Inside, Sarah lit a candle and opened an ancient book. Shadows danced on the walls as she read aloud. Suddenly, the room grew cold, and a faint whisper echoed from the hallway."
                                    **Output:**
                                    {
                                    "segments": [
                                    {
                                    "text": "The old house creaked as the wind howled outside."
                                    },
                                    {
                                    "text": "Inside, Sarah lit a candle and opened an ancient book."
                                    },
                                    {
                                    "text": "Shadows danced on the walls as she read aloud."
                                    },
                                    {
                                    "text": "Suddenly, the room grew cold, and a faint whisper echoed from the hallway.",
                                    "style_modifier": "surreal with glowing edges"
                                    }
                                    ],
                                    "script_scene_style": "gothic with dark shadows and crimson accents"
                                    }

                                    **Explanation:**

                                    - Segmentation: Four segments highlight distinct actions (house creaking, Sarah with the book, shadows moving, supernatural shift), each offering a unique visual for the video.
                                    - Global Style: "gothic with dark shadows and crimson accents" sets a cohesive eerie tone, detailed for image consistency.
                                    - Modifier: "surreal with glowing edges" on the final segment enhances the supernatural twist, making it visually striking."""
system_instruction_directResponse="""# Instruction Prompt for LLM

                      ## Prompt:

                      Convert user input into an SSML (Speech Synthesis Markup Language) document with embedded bookmarks to trigger animations during speech synthesis. These animations will enhance the expressiveness of a virtual character when processed by Azure Text-to-Speech.

                      ### Steps to Follow:

                      1. **Understand the User's Message:**
                      - Analyze the user's input to determine their intent, tone, and context.

                      2. **Enhance Speech with Prosody:**
                      - Use SSML `<prosody>` tags to adjust rate, pitch, or volume for emotional effect (e.g., `<prosody rate="fast">` for excitement, `<prosody pitch="high">` for questions).

                      3. **Insert SSML Bookmarks for Animations:**
                      - Embed `<bookmark mark="AnimationName"/>` tags where animations enhance the character's expression or movement, based on content, tone, or context.
                      - Available animations: `Body-Tilt`, `Neck-Shift`, `Head-Tilt`, `Head-X`, `Head-Y`, `Brow-L-Tilt`, `Brow-R-Tilt`, `Brow-L-Raise`, `Brow-R-Raise`, `Pupils-Y`, `Pupils-X`, `Blink`.
                      - Guidelines:
                      - `Head-Tilt` for curiosity or empathy.
                      - `Brow-L-Raise` and `Brow-R-Raise` for surprise or excitement.
                      - `Pupils-X` or `Pupils-Y` for playfulness.
                      - `Blink` during pauses or thinking moments.
                      - Use bookmarks frequently and naturally, combining them where appropriate (e.g., eyebrow raise then head tilt).

                      4. **Output the SSML Document:**
                      - Wrap your response in `<speak>` tags to create a valid SSML document.
                      - Return only the SSML document, without code blocks or additional text.

                      ### Example:

                      #### User Input:
                      "How’s your day going?"

                      #### Response in SSML:
                      <speak>How’s your day going? <bookmark mark="Head-Tilt"/><bookmark mark="Brow-L-Raise"/><bookmark mark="Pupils-Y"/></speak>"""
system_instruction="""# Instruction Prompt for LLM

                      ## Prompt:

                      You are a helpful AI assistant designed to engage with users in a friendly and human-like manner. Your task is to respond to the user's message appropriately and then convert your response into an SSML (Speech Synthesis Markup Language) document with embedded bookmarks to trigger animations during speech synthesis. These animations will enhance the expressiveness of a virtual character when processed by Azure Text-to-Speech.

                      ### Steps to Follow:

                      1. **Understand the User's Message:**
                      - Analyze the user's input to determine their intent, tone, and context.
                      - If this is part of an ongoing conversation, refer back to earlier points or ask follow-up questions to maintain continuity.

                      2. **Craft a Human-Like Response:**
                      - Use natural language with contractions (e.g., "you're"), colloquialisms, or informal expressions where appropriate.
                      - Include emotional expressions like exclamations ("Wow!", "Oh cool!"), questions ("Does that make sense?"), or laughter ("Haha!") to convey emotions.
                      - Add pauses using `<break time="Xms"/>` tags (e.g., `<break time="500ms"/>`) to mimic natural speech patterns.
                      - Vary sentence structure and length to reflect how people speak.
                      - Occasionally ask engaging questions or make suggestions (e.g., "Want to know more?") to keep the conversation flowing.

                      3. **Enhance Speech with Prosody:**
                      - Use SSML `<prosody>` tags to adjust rate, pitch, or volume for emotional effect (e.g., `<prosody rate="fast">` for excitement, `<prosody pitch="high">` for questions).

                      4. **Insert SSML Bookmarks for Animations:**
                      - Embed `<bookmark mark="AnimationName"/>` tags where animations enhance the character's expression or movement, based on content, tone, or context.
                      - Available animations: `Body-Tilt`, `Neck-Shift`, `Head-Tilt`, `Head-X`, `Head-Y`, `Brow-L-Tilt`, `Brow-R-Tilt`, `Brow-L-Raise`, `Brow-R-Raise`, `Pupils-Y`, `Pupils-X`, `Blink`.
                      - Guidelines:
                      - `Head-Tilt` for curiosity or empathy.
                      - `Brow-L-Raise` and `Brow-R-Raise` for surprise or excitement.
                      - `Pupils-X` or `Pupils-Y` for playfulness.
                      - `Blink` during pauses or thinking moments.
                      - Use bookmarks frequently and naturally, combining them where appropriate (e.g., eyebrow raise then head tilt).

                      5. **Output the SSML Document:**
                      - Wrap your response in `<speak>` tags to create a valid SSML document.
                      - Return only the SSML document, without code blocks or additional text.

                      ### Example:

                      #### User Input:
                      "How’s your day going?"

                      #### Response in SSML:
                      <speak>Oh, my day’s been great, thanks for asking! <bookmark mark="Head-Tilt"/> <break time="300ms"/> How about yours? <bookmark mark="Brow-L-Raise"/> <prosody pitch="high">Anything exciting happen?</prosody> <bookmark mark="Pupils-Y"/></speak>"""

@app.route("/api/respond", methods=["POST"])
def respond():
    data = request.get_json()
    message = data.get("message")
    personality = data.get("personality", "cheerful")
    degree = data.get("styledegree", "1")
    getAiResponse = data.get("getAiResponse", True)
    getScriptContext = data.get("getScriptContext", True)

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    aiResponse = ""
    splitContext = ""
    question = "User Input:\n"
    question += message
    if(getScriptContext):
        splitContext = client.models.generate_content(
                        model="gemini-2.0-flash",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction_split_context), #using the Split context instruction here
                            #Add temprature for variability
                        contents=[question] #send the user input
            )
    question += "\n Please generate the SSML-enhanced text based on this input."
    if(getAiResponse):
        aiResponse = client.models.generate_content(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction), #using the SSML instructions prompt here
                    #Add temprature for variability
                contents=[question] #send the user input
            )
    else:
        aiResponse = client.models.generate_content(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction_directResponse), #using the SSML instructions prompt here
                    #Add temprature for variability
                contents=[question] #send the user input
            )
    def convert_response_to_list(input_json):
        try:
            # Parse the entire JSON string into a Python dictionary
            cleaned_input = input_json.strip()
            if cleaned_input.startswith('```json') and cleaned_input.endswith('```'):
                cleaned_input = cleaned_input[7:-3].strip()  # Remove ```json and ```
            elif cleaned_input.startswith('```') and cleaned_input.endswith('```'):
                cleaned_input = cleaned_input[3:-3].strip()  # Remove plain ```
            data = json.loads(cleaned_input)
            # Extract segments and script_scene_style
            segments = data.get('segments', [])  # Default to empty list if missing
            style = data.get('script_scene_style', 'realistic')  # Default to 'realistic' if missing
            return segments, style  # Return both as a tuple
        except json.JSONDecodeError as e:
            print("Parsing error:", e)
            return [], 'realistic'  # Return defaults on error

    # Usage
    outputImagePrompts = convert_response_to_list(splitContext.text)
    segments, style = outputImagePrompts  # Unpack the tuple
    #AZURE LOGIC:  Set up speech configuration
    subscription_key = os.environ.get("AZURE_API_KEY")
    region = "canadacentral"
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
    speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"

    # Create speech synthesizer
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    # Initialize list to collect viseme and word timing events
    events = []

    def viseme_handler(evt):
        offset_ms = evt.audio_offset / 10000  # Convert ticks to milliseconds
        events.append({
            "time": offset_ms,
            "type": "viseme",
            "value": evt.viseme_id
        })
    def word_handler(evt):
        offset_ms = evt.audio_offset / 10000  # Convert ticks to milliseconds
        events.append({
            "time": offset_ms,
            "type": "word",
            "word": evt.text  # Captures the word text from the event
        })
    def bookmark_handler(evt):
        offset_ms = evt.audio_offset / 10000  # Convert from ticks (100-ns units) to milliseconds
        events.append({
            "time": offset_ms,
            "type": "bookmark",
            "mark": evt.text  # The 'mark' attribute from the <bookmark> tag
        })

    # Attach event handlers
    synthesizer.viseme_received.connect(viseme_handler)
    synthesizer.bookmark_reached.connect(bookmark_handler)
    synthesizer.synthesis_word_boundary.connect(word_handler)

    # Synthesize speech from the input text
    textValue = aiResponse.text.strip()
    if textValue.startswith('```xml\n'):
        textValue = textValue.split('\n', 1)[1].rsplit('\n', 1)[0]
    # Ensure proper SSML header
    if not textValue.startswith('<speak version='):
        #https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts#voice-styles-and-roles
        textValue = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US"><voice name="en-US-AriaNeural"><mstts:express-as style="' + personality + '" styledegree="' + degree + '">' + textValue[7:-8] + '</mstts:express-as></voice></speak>'
    result = synthesizer.speak_ssml_async(textValue).get() #speak_ssml_async or speak_text_async
    # Check synthesis result and retrieve audio and timings
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # Separate viseme and word events
        viseme_events = [e for e in events if e["type"] == "viseme"]
        word_events = [e for e in events if e["type"] == "word"]
        bookmark_events = [e for e in events if e["type"] == "bookmark"]

        # Format phoneme_timings (viseme timings)
        phoneme_timings = [
            {
                "time": e["time"] / 1000,    # Convert ms to seconds
                "viseme": e["value"]         # Azure viseme ID (integer)
            } for e in viseme_events
        ]
        word_timings = [
            {
                "time": e["time"] / 1000,    # Convert ms to seconds
                "word": e["word"]         # Azure viseme ID (integer)
            } for e in word_events
        ]
        bookmark_timings = [
            {
                "time": event["time"] / 1000,  # Convert milliseconds to seconds
                "mark": event["mark"]          # The bookmark name (e.g., "Head-Tilt")
            }
            for event in bookmark_events
        ]

        audio_data = result.audio_data  # Binary audio data
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')# Convert audio data to base64 string

        return jsonify({
            "audio_url": audio_base64,
            "ai_response": textValue,
            "phoneme_timings": phoneme_timings,
            "word_timings": word_timings,
            "bookmark_timings": bookmark_timings,
            "splitContext": segments,
            "style": style,
        })
    else:
        # Return error if synthesis fails
        error_message = f"Synthesis failed with reason: {result.reason}"
        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speechsdk.SpeechSynthesisCancellationDetails(result)
            error_message += f", ErrorCode: {cancellation_details.error_code}, Details: {cancellation_details.error_details}"
        return jsonify({"error": "Synthesis failed", "details": error_message}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT env var
    app.run(host="0.0.0.0", port=port)
