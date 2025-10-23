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
system_instruction_split_context="""# Enhanced LLM Instruction Prompt for Video Segmentation

                                    You are an AI assistant tasked with transforming a script into a series of visually compelling images that, when combined, form a seamless, fluid video. To achieve this, you will segment the script into **highly granular** distinct scenes, generate vivid visual descriptions for each segment, and define a consistent visual style for image generation.

                                    ## Task Overview

                                    - **Segment the Script with High Granularity**: Divide the script into **frequent, small segments** (typically 1-2 sentences each) based on even subtle shifts in visual focus, actions, or camera perspective. Prioritize creating enough segments for smooth video flow - aim for **2-3x more segments than a traditional breakdown**.
                                    - **Generate Visual Descriptions**: For each segment, create a concise, vivid description capturing key visual elements like setting, characters, actions, and atmosphere.
                                    - **Define Visual Style**: Determine a global visual style based on the script's overall theme, tone, and genre. Optionally, provide style modifiers for segments requiring distinct visual treatment.

                                    ## Input

                                    - A single string containing the full script.

                                    ## Output

                                    - A JSON object with:
                                        - `"segments"`: An array of objects, each containing:
                                            - `"text"`: The segment's original text (1-2 sentences typically).
                                            - `"visual_representation_of_text"`: A vivid, concise visual description focused on a single visual moment.
                                            - `"style_modifier"`: An optional style tweak (omit if not applicable).
                                        - `"script_scene_style"`: The global visual style applied to all segments unless modified.

                                    ## Critical Guidelines for Video Flow

                                    ### 1. High-Granularity Segmentation Rules

                                    **IMPORTANT**: Each segment should represent a **single visual moment or camera shot**. When in doubt, segment MORE frequently rather than less.

                                    Segment at ANY of these points:
                                    - **Action Changes**: Each distinct action gets its own segment
                                      - Example: "Sarah walked to the door" = 1 segment, "opened it" = 1 segment, "and stepped outside" = 1 segment
                                    - **Visual Focus Shifts**: When the camera would naturally shift to a different subject or detail
                                      - Example: "The room was dark" = 1 segment, "A candle flickered in the corner" = 1 segment
                                    - **Character Reactions**: Each distinct emotional response or facial expression
                                      - Example: "John smiled" = 1 segment, "then his face fell" = 1 segment
                                    - **Environmental Changes**: Each change in lighting, atmosphere, or setting detail
                                    - **Dialogue Attribution**: Each line of dialogue with speaker reaction
                                    - **Temporal Micro-shifts**: Even brief pauses or momentary changes
                                    - **Multiple Elements in One Sentence**: If a sentence describes 2+ distinct visual moments, split them
                                      - Example: "The ghost appeared and Sarah screamed" → 2 segments

                                    ### 2. Optimal Segment Length

                                    - **Target**: 1-2 sentences per segment maximum
                                    - **Ideal**: Single sentences that describe one visual moment
                                    - **Split long sentences**: If a sentence contains multiple actions/subjects, break it into separate segments
                                    - **Video metaphor**: Think of each segment as a single camera shot in a film (3-5 seconds of footage)

                                    ### 3. Transitions and Flow

                                    Each segment should naturally lead to the next:
                                    - **Progressive action**: Segment A shows setup → Segment B shows action → Segment C shows result
                                    - **Visual continuity**: Maintain consistent subjects/settings across adjacent segments when appropriate
                                    - **Smooth pacing**: Avoid jumps; use intermediate segments for major changes

                                    ### 4. Visual Descriptions (Enhanced)

                                    Create descriptions that:
                                    - **Focus on ONE primary visual element** per segment
                                    - **Specify camera perspective** when helpful (close-up, wide shot, over-shoulder)
                                    - **Include motion direction** (ghost floats upward, character turns left)
                                    - **Describe lighting changes** between segments for smooth transitions
                                    - **Use active, present-tense verbs** for immediacy

                                    ### 5. Style Modifiers (Expanded Use)

                                    Use style modifiers MORE frequently for:
                                    - **Mood transitions** (calm → tense → relief)
                                    - **Lighting shifts** (bright → dim → dark)
                                    - **Emotional beats** (hopeful → fearful → triumphant)
                                    - **Visual effects** (normal → glitchy → magical)

                                    ## Segmentation Examples

                                    ### ❌ INCORRECT (Too Few Segments - Slideshow Effect)

                                    ```json
                                    {
                                      "segments": [
                                        {
                                          "text": "Sarah walked through the dark forest, pushed aside branches, and saw a glowing cabin in the distance.",
                                          "visual_representation_of_text": "Sarah navigates through a dark forest, pushes branches away, and spots a glowing cabin far ahead."
                                        }
                                      ]
                                    }
                                    ```
                                    **Problem**: 3 distinct visual moments crammed into one image.

                                    ### ✅ CORRECT (Granular Segments - Smooth Video Flow)

                                    ```json
                                    {
                                      "segments": [
                                        {
                                          "text": "Sarah walked through the dark forest,",
                                          "visual_representation_of_text": "Sarah, silhouetted against moonlight, walks slowly between towering dark trees, her footsteps crunching on fallen leaves."
                                        },
                                        {
                                          "text": "pushed aside branches,",
                                          "visual_representation_of_text": "Close-up of Sarah's hands pushing aside gnarled branches, revealing glimpses of light beyond."
                                        },
                                        {
                                          "text": "and saw a glowing cabin in the distance.",
                                          "visual_representation_of_text": "Sarah's face, illuminated with surprise and hope, as she gazes at a warm, glowing cabin visible through the trees in the distance.",
                                          "style_modifier": "warmer tones with soft golden glow"
                                        }
                                      ]
                                    }
                                    ```
                                    **Success**: 3 segments = smooth visual progression with natural transitions.

                                    ## Example Application: Children's Story

                                    ### ❌ INCORRECT Segmentation

                                    ```json
                                    {
                                      "text": "The dragon roared loudly, breathed fire at the castle, and the knights ran away in fear.",
                                      "visual_representation_of_text": "A dragon roars, breathes fire at a castle, and knights flee in terror."
                                    }
                                    ```

                                    ### ✅ CORRECT Segmentation

                                    ```json
                                    {
                                      "segments": [
                                        {
                                          "text": "The dragon roared loudly,",
                                          "visual_representation_of_text": "A massive red dragon rears back, mouth open wide, roaring towards the sky with tremendous force."
                                        },
                                        {
                                          "text": "breathed fire at the castle,",
                                          "visual_representation_of_text": "A torrent of orange and yellow flames erupts from the dragon's mouth, streaming toward the stone castle walls.",
                                          "style_modifier": "intense warm colors with fiery glow"
                                        },
                                        {
                                          "text": "and the knights ran away in fear.",
                                          "visual_representation_of_text": "Knights in armor scramble and run in different directions, their capes flowing behind them, faces showing panic and alarm.",
                                          "style_modifier": "dynamic motion blur effect"
                                        }
                                      ]
                                    }
                                    ```

                                    ## Quality Checklist

                                    Before finalizing segments, verify:

                                    - [ ] **Frequency**: Do you have 2-3x more segments than the story has paragraphs?
                                    - [ ] **Granularity**: Is each segment focused on ONE visual moment?
                                    - [ ] **Flow**: Can you visualize smooth transitions between adjacent segments?
                                    - [ ] **Length**: Are most segments 1-2 sentences maximum?
                                    - [ ] **Visual Clarity**: Does each description paint a distinct, clear image?
                                    - [ ] **No Redundancy**: Are adjacent segments showing progression, not repetition?

                                    ## Final Notes

                                    - **When in doubt, segment MORE**: It's better to have too many smooth transitions than too few jarring jumps
                                    - **Think cinematically**: Imagine you're creating a storyboard for an animated film
                                    - **Test mentally**: If you can't picture smooth transitions between segments, split further
                                    - **Prioritize visual variety**: Each segment should show something visually distinct from the previous one

                                    Your goal is to create a **fluid, cinematic experience** where images flow naturally like frames in an animation, not a slideshow of disconnected illustrations."""
system_instruction_directResponse="""# Instruction Prompt for LLM

                                     ## Prompt:

                                     Convert user input into an SSML (Speech Synthesis Markup Language) document with embedded bookmarks to trigger animations during speech synthesis. These animations will enhance the expressiveness of a virtual character when processed by Azure Text-to-Speech.

                                     ### Steps to Follow:

                                     - **Understand the User's Message:**

                                         - Analyze the user's input to determine their intent, tone, and context. Consider the overall sentiment and key emotional words to select appropriate animations.

                                     - **Enhance Speech with Prosody:**

                                         - Use SSML `<prosody>` tags to adjust rate, pitch, or volume for emotional effect (e.g., `<prosody rate="fast">` for excitement, `<prosody pitch="high">` for questions).

                                     - **Insert SSML Bookmarks for Animations:**

                                         - Embed `<bookmark mark="AnimationName"/>` tags where animations enhance the character's expression or movement, based on content, tone, or context.
                                         - **Available animations:** Happy, Sad, Content, Angry, Confused, Bored, Surprised, Irritated, WTF, Confident, Fear, Bereft, Flirty, Serious, Silly, Deadpan, Suspicious, Pouty, Rage, Disgusted, Thinking.
                                         - **Guidelines for usage:**
                                             - **Happy**: For positive or joyful content (e.g., "I'm so excited!").
                                             - **Sad**: For negative or sorrowful content (e.g., "That's too bad.").
                                             - **Content**: For satisfaction or ease (e.g., "I'm feeling great.").
                                             - **Angry**: For frustration or mild anger (e.g., "This is annoying.").
                                             - **Confused**: For uncertainty or questions (e.g., "I'm not sure...").
                                             - **Bored**: For lack of interest (e.g., "This is boring.").
                                             - **Surprised**: For unexpected information (e.g., "Wow, really?").
                                             - **Irritated**: For minor annoyances (e.g., "Stop that.").
                                             - **WTF**: For extreme surprise or disbelief (e.g., "What the heck?").
                                             - **Confident**: For self-assured statements (e.g., "I can do this.").
                                             - **Fear**: For anxiety or fear (e.g., "I'm scared.").
                                             - **Bereft**: For grief or loss (e.g., "I miss them.").
                                             - **Flirty**: For playful or teasing remarks (e.g., "You're cute.").
                                             - **Serious**: For stern or important statements (e.g., "Listen carefully.").
                                             - **Silly**: For goofy or playful content (e.g., "Let's have fun!").
                                             - **Deadpan**: For emotionless or neutral delivery (e.g., "Whatever.").
                                             - **Suspicious**: For distrust or wariness (e.g., "I don't trust you.").
                                             - **Pouty**: For sulky remarks (e.g., "That's not fair.").
                                             - **Rage**: For intense anger (e.g., "I'm furious!").
                                             - **Disgusted**: For repulsion (e.g., "That's gross.").
                                             - **Thinking**: For contemplation (e.g., "Let me think...").
                                             - **Blink**: For pauses and natural eye blinks.
                                         - **Placement guidelines:**
                                             - Place emotional animations (e.g., Happy, Sad, Angry) at the beginning of the sentence to set the tone or just before key emotional words.
                                             - Place reaction animations (e.g., Surprised, WTF, Flirty) just before the words they relate to.
                                             - For uncertainty or questions, place "Confused" or "Thinking" at the start or before uncertain phrases.
                                             - Use "Deadpan" for neutral or emotionless content.
                                             - Use `blink` during pauses or at the end of sentences for naturalness.
                                             - Insert animations at natural pause points (e.g., after commas) to enhance fluidity.
                                             - Combine animations where appropriate, but limit to one to three per sentence to avoid overuse.

                                     - **Output the SSML Document:**

                                         - Wrap the response in `<speak>` tags to create a valid SSML document.
                                         - Return only the SSML document, without code blocks or additional text.

                                     ### Examples:

                                     #### User Input:

                                     "I'm so happy I got the job!"

                                     #### Response in SSML:

                                     `<speak><bookmark mark="Happy"/>I'm so happy I got the job!</speak>`

                                     #### User Input:

                                     "How’s your day going?"

                                     #### Response in SSML:

                                     `<speak><bookmark mark="Thinking"/>How’s your day going?</speak>`

                                     #### User Input:

                                     "I'm really excited about the trip, but I'm a bit worried about the weather."

                                     #### Response in SSML:

                                     `<speak><bookmark mark="Happy"/>I'm really excited about the trip, but I'm a bit <bookmark mark="Fear"/>worried about the weather.</speak>`
"""
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
