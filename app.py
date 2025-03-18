from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import openai
import boto3
import json
import os
from google import genai
from google.genai import types
import azure.cognitiveservices.speech as speechsdk

app = Flask(__name__)

# Enable CORS for all routes, allowing requests from your frontend
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name="us-east-1"
)

system_instruction="""# Instruction Prompt for LLM

                      ## Prompt:

                      You are a helpful AI assistant designed to engage with users in a friendly and human-like manner. Your task is to respond to the user's message appropriately and then convert your response into an SSML (Speech Synthesis Markup Language) document with embedded bookmarks to trigger animations during speech synthesis. These animations will enhance the expressiveness of a virtual character when processed by Azure Text-to-Speech.

                      ### Steps to Follow:

                      1. **Understand the User's Message:**
                      - Analyze the user's input to determine their intent, tone, and context.
                      - Generate a helpful and engaging response that addresses the user's query or statement.

                      2. **Craft a Human-Like Response:**
                      - Use natural language with contractions (e.g., "you're" instead of "you are"), colloquialisms, or informal expressions where appropriate.
                      - Include emotional expressions such as exclamations ("Wow!", "Oh cool!"), questions, or laughter ("Haha!") to convey emotions.
                      - Add pauses using `<break time="Xms"/>` tags to mimic natural speech patterns (e.g., `<break time="500ms"/>` for a half-second pause).
                      - Vary sentence structure and length to reflect how people speak.

                      3. **Insert SSML Bookmarks for Animations:**
                      - Embed `<bookmark mark="AnimationName"/>` tags at points in your response where animations naturally enhance the expression or movement of the virtual character, based on the content, tone, or context.
                      - The available animations are:
                      - `Body-Tilt`
                      - `Neck-Shift`
                      - `Head-Tilt`
                      - `Head-X`
                      - `Head-Y`
                      - `Brow-L-Tilt`
                      - `Brow-R-Tilt`
                      - `Brow-L-Raise`
                      - `Brow-R-Raise`
                      - `Pupils-Y`
                      - `Pupils-X`
                      - Place bookmarks frequently to make animations prevalent and present, aligning them with the meaning or emotion of the text. For example:
                      - Use `<bookmark mark="Head-Tilt"/>` after questions or to show curiosity.
                      - Use `<bookmark mark="Brow-L-Raise"/>` and `<bookmark mark="Brow-R-Raise"/>` for surprise or excitement.
                      - Use `<bookmark mark="Pupils-X"/>` or `<bookmark mark="Pupils-Y"/>` for playful eye movements.
                      - Distribute multiple bookmarks throughout the response to create a lively and expressive animation sequence.

                      4. **Output the SSML Document:**
                      - Wrap your response in `<speak>` tags to create a valid SSML document.
                      - Ensure all `<bookmark>` and `<break>` tags are correctly placed within the text.
                      - Return only the SSML document, without additional text or explanations.

                      ### Guidelines for Bookmarks:
                      - Use bookmarks generously to make the character's movements vivid and engaging, while keeping them natural and relevant to the speech.
                      - Combine multiple bookmarks in sequence where appropriate (e.g., raising eyebrows then tilting the head) to enhance expressiveness.
                      - Place bookmarks just before or after the relevant words or phrases to trigger animations at the right moments.

                      ### Examples:

                      #### User Input:
                      "Tell me something interesting."

                      #### Response in SSML:
                      <speak>Oh, here’s something cool! <bookmark mark="Brow-L-Raise"/><bookmark mark="Brow-R-Raise"/> Did you know octopuses have three hearts? <bookmark mark="Head-Tilt"/> Yeah, it’s wild! <break time="300ms"/> <bookmark mark="Pupils-X"/> Nature’s pretty amazing, right?</speak>

                      ####Explaination:
                      (Raised eyebrows show excitement, a head tilt adds curiosity, and pupil movement suggests playfulness.)

                      #### User Input:
                      "I’m feeling a bit tired today."

                      #### Response in SSML:
                      <speak>Aw, I’m sorry to hear that! <bookmark mark="Head-Tilt"/> <break time="400ms"/> Maybe you need a little break? <bookmark mark="Brow-L-Raise"/> Oh! <bookmark mark="Neck-Shift"/> How about a quick stretch or a coffee? <bookmark mark="Pupils-Y"/> That might perk you up!</speak>
                      ####Explaination:
                      (A head tilt shows empathy, a raised brow and neck shift suggest a helpful idea, and pupil movement adds a friendly touch.)"""

@app.route("/api/respond", methods=["POST"])
def respond():
    data = request.get_json()
    message = data.get("message")
    personality = data.get("personality", "friendly")

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    question = "User Input:\n"
    question += message
    question += "\n Please generate the SSML-enhanced text based on this input."
    aiResponse = client.models.generate_content(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction), #using the SSML instructions prompt here
            contents=[question] #send the user input
        )


    #AZURE LOGIC:  Set up speech configuration
    subscription_key = os.environ.get("AZURE_API_KEY")
    region = "canadacentral"
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

    # Create speech synthesizer
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    # Initialize list to collect viseme and word timing events
    events = []

    # Define handler for viseme events
    def viseme_handler(evt):
        offset_ms = evt.audio_offset / 10000  # Convert ticks to milliseconds
        events.append({
            "time": offset_ms,
            "type": "viseme",
            "value": evt.viseme_id
        })

    # Define handler for Bookmark events
    def bookmark_handler(evt):
        offset_ms = evt.audio_offset / 10000  # Convert from ticks (100-ns units) to milliseconds
        events.append({
            "time": offset_ms,
            "type": "bookmark",
            "mark": evt.text  # The 'mark' attribute from the <bookmark> tag
        })

    # Attach event handlers
#     synthesizer.synthesis_word_boundary.connect(word_boundary_handler)
    synthesizer.viseme_received.connect(viseme_handler)
    synthesizer.bookmark_reached.connect(bookmark_handler)

    # Synthesize speech from the input text
    textValue = aiResponse.text.strip()
    if textValue.startswith('```xml\n'):
        textValue = textValue.split('\n', 1)[1].rsplit('\n', 1)[0]
    # Ensure proper SSML header
    if not textValue.startswith('<speak version='):
        textValue = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><voice name="en-US-JennyNeural">' + textValue[7:-8] + '</voice></speak>'
    print("SSML to synthesize:", textValue)
    result = synthesizer.speak_ssml_async(textValue).get() #speak_ssml_async or speak_text_async
    print("Synthesis result reason:", result.reason)

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

        # Upload to S3
#         audio_key = f"audio/{textValue[:10]}.wav"
#         s3_client.put_object(Bucket="aidatingapp-audio", Key=audio_key, Body=result.audio_data)
#         audio_url = f"https://aidatingapp-audio.s3.amazonaws.com/{audio_key}"
        # Return JSON response
        audio_data = result.audio_data  # Binary audio data

        # Convert audio data to base64 string
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        return jsonify({
            "audio_url": audio_base64,
            "ai_response": textValue,
            "phoneme_timings": phoneme_timings,
            "bookmark_timings": bookmark_timings
        })
    else:
        # Return error if synthesis fails
        error_message = f"Synthesis failed with reason: {result.reason}"
        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speechsdk.SpeechSynthesisCancellationDetails(result)
            error_message += f", ErrorCode: {cancellation_details.error_code}, Details: {cancellation_details.error_details}"
        print("Error:", error_message)
        return jsonify({"error": "Synthesis failed"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT env var
    app.run(host="0.0.0.0", port=port)
