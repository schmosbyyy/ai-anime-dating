from flask import Flask, request, jsonify
import openai
import boto3
import json
import os

app = Flask(__name__)

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

@app.route("/api/respond", methods=["POST"])
def respond():
    data = request.get_json()
    message = data.get("message")
    personality = data.get("personality", "friendly")

    # # Generate response with OpenAI
    # prompt = f"You are an avatar with a {personality} personality. User says: {message}. Respond:"
    # response = openai.Completion.create(
    #     engine="text-davinci-003",
    #     prompt=prompt,
    #     max_tokens=50
    # )
    # response_text = response.choices[0].text.strip()

    # Generate audio with Amazon Polly
    polly_response = polly_client.synthesize_speech(
        Text=message, #response_text,
        OutputFormat="mp3",
        VoiceId="Joanna"
    )
    audio = polly_response["AudioStream"].read()

    # Upload to S3
    audio_key = f"audio/{message[:10]}.mp3"
    s3_client.put_object(Bucket="aidatingapp-audio", Key=audio_key, Body=audio)
    audio_url = f"https://aidatingapp-audio.s3.amazonaws.com/{audio_key}"

    # Get phoneme timings
    speech_marks_response = polly_client.synthesize_speech(
        Text= message,#response_text,
        OutputFormat="json",
        VoiceId="Joanna",
        SpeechMarkTypes=["viseme"]
    )
    speech_marks = speech_marks_response["AudioStream"].read().decode().splitlines()
    timings = [{"time": float(json.loads(m)["time"]) / 1000, "viseme": json.loads(m)["value"]}
               for m in speech_marks]

    return jsonify({"audio_url": audio_url, "phoneme_timings": timings})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT env var
    app.run(host="0.0.0.0", port=port)