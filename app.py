from flask import Flask, request, jsonify
from flask_cors import CORS
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

system_instruction="""Instruction Prompt for LLM
                      Prompt:

                      You are an AI assistant tasked with enhancing a given text paragraph by embedding SSML (Speech Synthesis Markup Language) bookmarks. These bookmarks will trigger specific animations during speech synthesis when processed by Azure Text-to-Speech. The available animations are:

                      Body-Tilt
                      Neck-Shift
                      Head-Tilt
                      Head-X
                      Head-Y
                      Brow-L-Tilt
                      Brow-R-Tilt
                      Brow-L-Raise
                      Brow-R-Raise
                      Pupils-Y
                      Pupils-X
                      Your task is to:

                      Analyze the input text paragraph.
                      Insert SSML <bookmark mark="AnimationName"/> tags at appropriate points where the corresponding animation would naturally enhance the expression or movement of a speaking character, based on the text’s content, tone, or context.
                      Ensure the output is a valid SSML document by wrapping the modified text in <speak> tags.
                      Guidelines for Inserting Bookmarks:

                      Place bookmarks where animations align with the meaning or emotion of the text. For example:
                      Use <bookmark mark="Head-Tilt"/> after questions or when the text implies curiosity or contemplation.
                      Use <bookmark mark="Brow-L-Raise"/> and <bookmark mark="Brow-R-Raise"/> for surprise, excitement, or emphasis.
                      Use <bookmark mark="Pupils-X"/> or <bookmark mark="Pupils-Y"/> for subtle eye movements, such as shifting focus.
                      Use other animations like Body-Tilt or Neck-Shift to reflect physical gestures that match the dialogue’s intent.
                      Distribute animations naturally to make the character appear lifelike, avoiding overuse in short spans unless the context justifies it.

                      Output Format:
                      Return only the SSML document, starting with <speak> and ending with </speak>, with embedded <bookmark mark="AnimationName"/> tags.
                      Examples:

                      Input:
                      "Hello, how are you? I hope you're doing well."
                      Output:
                      <speak>Hello, how are you? <bookmark mark="Head-Tilt"/> I hope you're doing well.</speak>
                      (A head tilt is added after the question to suggest curiosity.)
                      Input:
                      "That’s amazing! I didn’t expect that at all."
                      Output:
                      <speak>That’s amazing! <bookmark mark="Brow-L-Raise"/><bookmark mark="Brow-R-Raise"/> I didn’t expect that at all.</speak>
                      (Raised eyebrows emphasize the surprise at "amazing.")
                      Input Text to Enhance:"""

@app.route("/api/respond", methods=["POST"])
def respond():
    data = request.get_json()
    message = data.get("message")
    personality = data.get("personality", "friendly")

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    question = "Input:\n"
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
        audio_key = f"audio/{textValue[:10]}.wav"
        s3_client.put_object(Bucket="aidatingapp-audio", Key=audio_key, Body=result.audio_data)
        audio_url = f"https://aidatingapp-audio.s3.amazonaws.com/{audio_key}"
        # Return JSON response
        print(textValue)
        print(phoneme_timings)
        print(bookmark_timings)

        return jsonify({
            "audio_url": audio_url,
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
