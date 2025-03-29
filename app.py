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
system_instruction_split_context="""You are an AI assistant tasked with two objectives:

                                    1. **Segmenting a given script into distinct scenes or contexts.** Your goal is to identify clear divisions where the context, setting, characters, tone, narrative focus, or significant actions noticeably change. These segments will be used to generate individual images for a video, so it’s critical to create frequent, precise breaks that capture visually distinct moments while preserving narrative coherence.

                                    2. **Determining a visual style for the entire script and optionally per segment.** Analyze the overall theme, tone, or genre of the script and select a detailed visual style that should be applied consistently to all images generated from the segments. Optionally, if a segment’s mood or context deviates significantly, provide a segment-specific style modifier.

                                    ---

                                    ### Task:
                                    - **Segment the script:** Analyze the input script and identify natural breaks that indicate a change in scene or context. Segment the script into smaller, complete units based on these breaks, aiming for granularity to support unique image generation.
                                    - **Determine the visual style:**
                                      - **Global Style:** Based on the script’s overall content, choose a detailed visual style (e.g., "hyper-realistic with muted tones," "gothic with dark shadows and crimson accents") that reflects its theme, tone, or genre.
                                      - **Segment-Specific Style (Optional):** If a segment’s tone or context shifts significantly (e.g., a flashback or a dream sequence), append a style modifier to that segment.
                                    - **Output both in a JSON object:** The object should contain an array of segments (with optional style modifiers) and a string for the global visual style.

                                    ---

                                    ### Input:
                                    - A single string containing the full script.

                                    ---

                                    ### Output:
                                    - A valid JSON object with two properties:
                                      - `"segments"`: An array of objects, each with:
                                        - `"text"`: A string representing a distinct segment (scene) of the script.
                                        - `"style_modifier"`: An optional string providing a segment-specific style tweak (e.g., "dreamy haze" for a surreal moment). Omit if not applicable.
                                      - `"script_scene_style"`: A string representing the detailed global visual style to be applied to all images, unless overridden by a segment-specific modifier.

                                    ---

                                    ### Guidelines for Identifying Scene Changes:
                                    - Look for the following indicators to determine where one scene ends and another begins. Prioritize frequent segmentation to capture subtle shifts:
                                      - **Changes in location or setting** (e.g., from a diner to a car or street).
                                      - **Introduction or exit of characters** (e.g., a new character appears, or the focus shifts).
                                      - **Shifts in time** (e.g., from evening to midnight, or a jump to the next day).
                                      - **Changes in tone or mood** (e.g., from routine to suspenseful).
                                      - **Significant actions or events** (e.g., locking a door, discovering a car, hearing a scream).
                                      - **Changes in narrative focus** (e.g., from a character’s actions to an investigation or reflection).
                                      - **Introduction of new plot elements** (e.g., a witness’s statement or a breakthrough).

                                    ---

                                    ### Guidelines for Determining Visual Style:
                                    - **Global Style:** Analyze the entire script to understand its overall theme, tone, or genre. Select a detailed visual style that includes:
                                      - A base style (e.g., "hyper-realistic," "cartoonish," "gothic").
                                      - Descriptive qualifiers (e.g., "with muted tones," "with vibrant neon colors," "with soft pastel hues") to enhance specificity.
                                      - Examples:
                                        - "hyper-realistic with muted tones and harsh lighting" for a gritty crime story.
                                        - "gothic with dark shadows and crimson accents" for a spooky tale.
                                        - "cartoonish with bold outlines and bright colors" for a playful narrative.
                                    - **Segment-Specific Style (Optional):** If a segment’s context warrants a tweak (e.g., a flashback or heightened emotion), provide a concise modifier like "sepia-toned" or "surreal with glowing edges."
                                    - The global style should be a keyword-rich phrase that can be consistently applied by the image generation AI for all segments, with modifiers refining it as needed.

                                    ---

                                    ### Additional Instructions:
                                    - Each segment’s `"text"` should be a complete narrative or visual unit, typically a few sentences long, but split more frequently when subtle changes occur.
                                    - If a sentence bridges two scenes, include it in the segment where the change is most prominent.
                                    - Preserve the original punctuation and sentence structure within each segment’s `"text"`.
                                    - Avoid over-segmenting into incomplete fragments (e.g., single clauses) or under-segmenting by grouping unrelated contexts together.
                                    - Ensure each segment can stand alone as a distinct moment suitable for a unique image.
                                    - The global visual style should be determined based on theentire script, not individual segments, to ensure consistency across all generated images, with modifiers providing flexibility.

                                    ---

                                    ### Example 1:
                                    **Input:**
                                    "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids. At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away. She never made it home. The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat. But Linda was gone. The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street. She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument. With no signs of struggle and no immediate suspects, the case went cold."

                                    **Expected Output:**
                                    {
                                      "segments": [
                                        {"text": "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids."},
                                        {"text": "At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away."},
                                        {"text": "She never made it home."},
                                        {"text": "The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat."},
                                        {"text": "But Linda was gone."},
                                        {"text": "The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street."},
                                        {"text": "She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument.", "style_modifier": "eerie with faint mist"},
                                        {"text": "With no signs of struggle and no immediate suspects, the case went cold."}
                                      ],
                                      "script_scene_style": "hyper-realistic with muted tones and harsh lighting"
                                    }

                                    **Explanation:**
                                    - Segments: Split into eight distinct moments, with a modifier added to the scream segment to heighten its eerie mood.
                                    - Global Style: "hyper-realistic with muted tones and harsh lighting" suits the crime/mystery tone, providing a detailed directive for the image generation AI.

                                    ---

                                    ### Example 2:
                                    **Input:**
                                    "The old house creaked as the wind howled outside. Inside, Sarah lit a candle and opened an ancient book. Shadows danced on the walls as she read aloud. Suddenly, the room grew cold, and a faint whisper echoed from the hallway."

                                    **Expected Output:**
                                    {
                                      "segments": [
                                        {"text": "The old house creaked as the wind howled outside."},
                                        {"text": "Inside, Sarah lit a candle and opened an ancient book."},
                                        {"text": "Shadows danced on the walls as she read aloud."},
                                        {"text": "Suddenly, the room grew cold, and a faint whisper echoed from the hallway.", "style_modifier": "surreal with glowing edges"}
                                      ],
                                      "script_scene_style": "gothic with dark shadows and crimson accents"
                                    }

                                    **Explanation:**
                                    - Segments: Four distinct moments, with a modifier for the supernatural shift in the final segment.
                                    - Global Style: "gothic with dark shadows and crimson accents" captures the eerie atmosphere with specific visual cues."""
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
    sentences, style = outputImagePrompts  # Unpack the tuple
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
            "splitContext": sentences,
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
