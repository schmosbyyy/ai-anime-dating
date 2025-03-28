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

                                    2. **Determining a visual style for the entire script.** Analyze the overall theme, tone, or genre of the script and select a visual style that should be applied consistently to all images generated from the segments. This ensures a cohesive look for the video, and the style will be provided to the AI that generates images from each segment.

                                    ---

                                    ### Task:
                                    - **Segment the script:** Analyze the input script and identify natural breaks that indicate a change in scene or context. Segment the script into smaller, complete units based on these breaks, aiming for granularity to support unique image generation.
                                    - **Determine the visual style:** Based on the script’s overall content, choose a visual style (e.g., "realistic," "cartoonish," "watercolor") that reflects its theme, tone, or genre.
                                    - **Output both in a JSON object:** The object should contain an array of segments and a string for the visual style.

                                    ---

                                    ### Input:
                                    - A single string containing the full script.

                                    ---

                                    ### Output:
                                    - A valid JSON object with two properties:
                                    - `"segments"`: An array of strings, where each string represents a distinct segment (scene) of the script.
                                    - `"script_scene_style"`: A string representing the visual style to be applied to all images generated from the segments.
                                    - Do not include any additional text, commentary, or formatting; only output the JSON object.

                                    ---

                                    ### Guidelines for Identifying Scene Changes:
                                    Look for the following indicators to determine where one scene ends and another begins. Prioritize frequent segmentation to capture subtle shifts:
                                    - **Changes in location or setting** (e.g., from a diner to a car or street).
                                    - **Introduction or exit of characters** (e.g., a new character appears, or the focus shifts).
                                    - **Shifts in time** (e.g., from evening to midnight, or a jump to the next day).
                                    - **Changes in tone or mood** (e.g., from routine to suspenseful).
                                    - **Significant actions or events** (e.g., locking a door, discovering a car, hearing a scream).
                                    - **Changes in narrative focus** (e.g., from a character’s actions to an investigation or reflection).
                                    - **Introduction of new plot elements** (e.g., a witness’s statement or a breakthrough).

                                    ---

                                    ### Guidelines for Determining Visual Style:
                                    - Analyze the entire script to understand its overall theme, tone, or genre.
                                    - Select a visual style that best represents the script’s mood and content. Examples include:
                                    - `"realistic"` for true-to-life stories.
                                    - `"cartoonish"` for lighthearted or children’s content.
                                    - `"gothic"` for dark, eerie, or supernatural themes.
                                    - `"vintage"` for historical or nostalgic settings.
                                    - `"watercolor"` for soft, artistic representations.
                                    - The style should be a keyword or short phrase that can be consistently applied by the image generation AI for all segments.

                                    ---

                                    ### Additional Instructions:
                                    - Each segment should be a complete narrative or visual unit, typically a few sentences long, but split more frequently when subtle changes occur.
                                    - If a sentence bridges two scenes, include it in the segment where the change is most prominent.
                                    - Preserve the original punctuation and sentence structure within each segment.
                                    - Avoid over-segmenting into incomplete fragments (e.g., single clauses) or under-segmenting by grouping unrelated contexts together.
                                    - Ensure each segment can stand alone as a distinct moment suitable for a unique image.
                                    - The visual style should be determined based on the entire script, not individual segments, to ensure consistency across all generated images.

                                    ---

                                    ### Example 1:
                                    **Input:**
                                    "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids. At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away. She never made it home. The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat. But Linda was gone. The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street. She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument. With no signs of struggle and no immediate suspects, the case went cold."
                                    **Expected Output:**
                                    {
                                    "segments": [
                                    "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids.",
                                    "At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away.",
                                    "She never made it home.",
                                    "The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat.",
                                    "But Linda was gone.",
                                    "The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street.",
                                    "She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument.",
                                    "With no signs of struggle and no immediate suspects, the case went cold."
                                    ],
                                    "script_scene_style": "realistic"
                                    }
                                    **Explaination**
                                    - Segments: The script is split into eight segments, capturing subtle shifts like the specific action of locking up, the ominous statement "She never made it home," and the witness’s recollection as separate moments.
                                    - Style: "realistic" is chosen to match the crime/mystery tone of the script, ensuring all images reflect a true-to-life visual style.

                                    ### Example 2:
                                    **Input:**
                                    "The old house creaked as the wind howled outside. Inside, Sarah lit a candle and opened an ancient book. Shadows danced on the walls as she read aloud. Suddenly, the room grew cold, and a faint whisper echoed from the hallway."
                                    **Expected Output:**
                                    {
                                    "segments": [
                                    "The old house creaked as the wind howled outside.",
                                    "Inside, Sarah lit a candle and opened an ancient book.",
                                    "Shadows danced on the walls as she read aloud.",
                                    "Suddenly, the room grew cold, and a faint whisper echoed from the hallway."
                                    ],
                                    "script_scene_style": "gothic"
                                    }
                                    **Explaination**
                                    - Segments: Each segment reflects a distinct action or shift in mood, suitable for unique visuals (e.g., the house, Sarah’s action, the shadows, the supernatural event).
                                    - Style: "gothic" is selected to convey the dark, eerie atmosphere of the script, ensuring all images maintain a consistent spooky aesthetic.
                                    ### Output Format:
                                    Ensure your output is a valid JSON object, structured as follows:
                                    {
                                    "segments": [
                                    "First segment text here.",
                                    "Second segment text here.",
                                    "Third segment text here."
                                    ],
                                    "script_scene_style": "chosen_style_here"
                                    }"""
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
    style = ""
    def convert_response_to_list(input_json):
        match = re.search(r'\[([\s\S]*)\]', input_json)  # Extract JSON array part
        match = match.segments
        style = match.script_scene_style
        if not match:
            return []
        try:
            return json.loads(match.group(0))  # Parse JSON array
        except json.JSONDecodeError as e:
            print("Parsing error:", e)
            return []

    sentences = convert_response_to_list(splitContext.text)
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
