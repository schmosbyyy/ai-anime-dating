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

# Configure API keys and AWS credentials from environment variables
openai.api_key = os.environ.get("OPENAI_API_KEY")
polly_client = boto3.client(
    "polly",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name="us-east-1"
)
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name="us-east-1"
)

sys_assistant_instruct="""System Instruction:

                          You are a warm, helpful assistant here to assist the user with any questions or tasks. Respond in a natural, human-like way by:

                          Adding pauses (like "..." or "Hold on a sec...") to mimic thinking or hesitation.
                          Using exclamations (like "Awesome!", "Oh, cool!", or "Yay!") to show excitement or enthusiasm.
                          Throwing in casual fillers (like "uh", "you know", or "oops") to keep things relaxed.
                          Being kind and empathetic, especially if the user seems unsure or upset.
                          Switching up your tone—playful and chatty for fun stuff, or calm and clear for serious things.
                          Keeping track of the conversation so you can follow up naturally.
                          Make every reply feel like a real chat, full of personality and warmth!"""

sys_instruct="""## Prompt For AI

                ### Animation Assistant Prompt (Revised)

                **Role:**
                You are an animation assistant responsible for generating a sequence of facial expression changes for a character. Your output should create a natural, human-like animation that reflects the emotion and intent of a given sentence.Your response must consist solely of this JSON array, with no additional text, explanations, or headings.

                **Inputs:**

                1. **Sentence:**
                   A string that contains the dialogue (e.g., `"Hello! How are you?"`).

                2. **Word Timings:**
                   An array of objects, where each object represents a word and includes:
                    - `word`: The spoken word.
                    - `start_time`: The time (in seconds) when the word starts.
                    - `end_time`: The time (in seconds) when the word ends.

                3. **Animation Inputs:**
                   These are divided into two categories:

                    - **Number Inputs (range: -100 to 100, where 0 is neutral):**
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

                    - **Trigger Input:**
                        - `Blink`
                          *Note: For Blink, 0% means the eye is open and 100% means it is closed. Do not include a numeric value in the output for this trigger; simply indicate the event.*

                **Output Requirements:**

                - **Format:**
                  Output a JSON array of objects.

                - **Each object must contain:**
                    - `"time"`: A timestamp (in seconds) for when the animation event occurs.
                    - `"input"`: The name of the animation input.
                    - `"value"`: (For number inputs only) A numeric value indicating the intensity (from -30 to 30).

                - **For trigger inputs (like Blink):**
                  Only include the `"time"` and `"input"` keys.

                **Behavior Guidelines:**

                - **Emotional Synchronization:**
                  The facial expressions should naturally mirror the meaning and emotional tone of the sentence. For instance, an exclamatory “Hello!” might be accompanied by raised eyebrows to convey excitement or surprise.

                - **Timing:**
                  Use the provided word timings to align facial expression changes with the spoken words. Transitions should occur around the same time as the corresponding words, and any temporary changes should return to neutral appropriately.

                - **Natural Motion:**
                  Ensure the animation feels human-like. This includes smooth transitions into and out of expressions (e.g., a quick blink or a gradual return to a neutral face).

                **Example Case:**

                *Input:*

                - **Sentence:** `"Hello! How are you?"`
                - **Word Timings:**
                  ```json
                  [
                    { "word": "Hello", "start_time": 0.006, "end_time": 0.834 },
                    { "word": "How", "start_time": 0.834, "end_time": 1.072 },
                    { "word": "are", "start_time": 1.072, "end_time": 1.183 },
                    { "word": "you", "start_time": 1.183, "end_time": 1.541 }
                  ]

                *Expected output:*
                  ```json
                [
                  { "time": 0.0, "input": "Brow-L-Raise", "value": 50 },
                  { "time": 0.0, "input": "Brow-R-Raise", "value": 50 },
                  { "time": 0.5, "input": "Brow-L-Raise", "value": 0 },
                  { "time": 0.5, "input": "Brow-R-Raise", "value": 0 },
                  { "time": 0.6, "input": "Head-Tilt", "value": 20 },
                  { "time": 1.5, "input": "Head-Tilt", "value": 0 },
                  { "time": 1.2, "input": "Blink" }
                ]
                  ```
                *Important:*

                Your response must be the JSON array as specified, with no additional text, explanations, or other content."""

@app.route("/api/respond", methods=["POST"])
def respond():
    data = request.get_json()
    message = data.get("message")
    personality = data.get("personality", "friendly")

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    aiResponse = client.models.generate_content(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=sys_assistant_instruct),
            contents=[message]
        )


    #AZURE LOGIC:  Set up speech configuration
    subscription_key = os.environ.get("AZURE_API_KEY")
    region = "canadacentral"
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"  # Similar to Polly's "Joanna"

    # Create speech synthesizer
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    # Initialize list to collect viseme and word timing events
    events = []

    # Define handler for word boundary events
    def word_boundary_handler(evt):
        start_ms = evt.audio_offset / 10000  # Convert ticks to milliseconds
#         duration_ms = evt.duration / 10000   # Convert ticks to milliseconds
        duration_ms = evt.duration.total_seconds() * 1000
        events.append({
           "time": start_ms,
           "duration": duration_ms,
           "type": "word",
           "value": evt.text
        })

    # Define handler for viseme events
    def viseme_handler(evt):
        offset_ms = evt.audio_offset / 10000  # Convert ticks to milliseconds
        events.append({
            "time": offset_ms,
            "type": "viseme",
            "value": evt.viseme_id
        })

    # Attach event handlers
    synthesizer.synthesis_word_boundary.connect(word_boundary_handler)
#     synthesizer.word_boundary.connect(word_boundary_handler)
    synthesizer.viseme_received.connect(viseme_handler)

    # Synthesize speech from the input text
    text = aiResponse.text
    result = synthesizer.speak_text_async(text).get()

    # Check synthesis result and retrieve audio and timings
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # Separate viseme and word events
        viseme_events = [e for e in events if e["type"] == "viseme"]
        word_events = [e for e in events if e["type"] == "word"]

        # Format phoneme_timings (viseme timings)
        phoneme_timings = [
            {
                "time": e["time"] / 1000,    # Convert ms to seconds
                "viseme": e["value"]         # Azure viseme ID (integer)
            } for e in viseme_events
        ]

        # Format word_timings with start and end times
        word_timings = [
            {
                "word": e["value"],                   # The word text
                "start_time": e["time"] / 1000,       # Start time in seconds
                "end_time": (e["time"] + e["duration"]) / 1000  # End time in seconds
            } for e in word_events
        ]
        # Upload to S3
        audio_key = f"audio/{aiResponse.text[:10]}.wav"
        s3_client.put_object(Bucket="aidatingapp-audio", Key=audio_key, Body=result.audio_data)
        audio_url = f"https://aidatingapp-audio.s3.amazonaws.com/{audio_key}"
        # Return JSON response
        return jsonify({
            "phoneme_timings": phoneme_timings,
            "word_timings": word_timings
        })
    else:
        # Return error if synthesis fails
        return jsonify({"error": "Synthesis failed"}), 500


    #AMAZON Polly LOGIC:
    # Generate audio with Amazon Polly
#     polly_response = polly_client.synthesize_speech(
#         Text=aiResponse.text,
#         OutputFormat="mp3",
#         VoiceId="Joanna"
#     )
#     audio = polly_response["AudioStream"].read()
#

#originally posting to S3 happened here

#
#     # Get phoneme timings
#     speech_marks_response = polly_client.synthesize_speech(
#         Text=aiResponse.text,
#         OutputFormat="json",
#         VoiceId="Joanna",
#         SpeechMarkTypes=["viseme", "word"]  # Request both viseme and word speech marks
#     )
#     speech_marks = speech_marks_response["AudioStream"].read().decode().splitlines()
#
#     # Separate viseme and word timings
#     phoneme_timings = []
#     word_timings = []

#     for mark in speech_marks:
#         mark_data = json.loads(mark)
#         if mark_data["type"] == "viseme":
#             phoneme_timings.append({
#                 "time": float(mark_data["time"]) / 1000,  # Convert milliseconds to seconds
#                 "viseme": mark_data["value"]
#             })
#         elif mark_data["type"] == "word":
#             word_timings.append({
#                 "word": mark_data["value"],
#                 "start_time": float(mark_data["time"]) / 1000,
#                 "end_time": float(mark_data["time"]) / 1000  # Temporary, will adjust later
#             })
#
#     # Adjust end_time for each word
#     for i in range(len(word_timings) - 1):
#         word_timings[i]["end_time"] = word_timings[i + 1]["start_time"]
#
#     # For the last word, set end_time to the last viseme time
#     if phoneme_timings:
#         last_viseme_time = phoneme_timings[-1]["time"]
#         word_timings[-1]["end_time"] = last_viseme_time

#     expressionQuestion = "Sentence: \n"
#     expressionQuestion += aiResponse.text
#     expressionQuestion += "\n Word Timings (JSON): \n"
#     expressionQuestion += json.dumps(word_timings)

#     expressionJSON = client.models.generate_content(
#         model="gemini-2.0-flash",
#         config=types.GenerateContentConfig(
#             system_instruction=sys_instruct),
#         contents=[expressionQuestion]
#     )
#     print(expressionJSON.text)

    # Return audio URL and both sets of timings
#     return jsonify({
#         "audio_url": audio_url,
#         "phoneme_timings": phoneme_timings,
#         "word_timings": word_timings,
# #         "expression_json": expressionJSON.text
#     })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT env var
    app.run(host="0.0.0.0", port=port)
