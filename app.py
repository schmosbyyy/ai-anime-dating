from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import openai
import json
import os
from google import genai
from google.genai import types
import azure.cognitiveservices.speech as speechsdk

app = Flask(__name__)

# Enable CORS for all routes, allowing requests from your frontend
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
system_instruction_split_context="""You are an AI assistant that processes scripts by segmenting them into meaningful contextual or scene-based divisions.

                                    ### Task:
                                    Given a script as input, return a JSON array where each item is a distinct segment of the script.

                                    ### Input:
                                    A single string containing the full script.

                                    ### Output:
                                    A valid JSON array of strings, with each string representing a distinct segment. Do not include any extra text, explanations, or formatting—only return a JSON array.

                                    ### Example:

                                    #### Input:
                                    "The sun rises over a quiet village. Birds chirp as villagers begin their day.
                                    A young boy runs through the fields, chasing a kite.
                                    Dark clouds gather, and thunder rumbles in the distance."

                                    #### Expected Output:
                                    ```json
                                    [
                                      "The sun rises over a quiet village. Birds chirp as villagers begin their day.",
                                      "A young boy runs through the fields, chasing a kite.",
                                      "Dark clouds gather, and thunder rumbles in the distance."
                                    ]"""
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
            "splitContext": splitContext.text,
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
