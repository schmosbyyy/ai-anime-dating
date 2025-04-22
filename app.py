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
system_instruction_split_context="""# Updated LLM Instruction Prompt

                                    You are an AI assistant tasked with transforming a script into a series of visually compelling images that, when combined, form a seamless video. To achieve this, you will segment the script into distinct scenes, generate vivid visual descriptions for each segment, and define a consistent visual style for image generation.

                                    ## Task Overview

                                    - **Segment the Script**: Divide the script into distinct scenes based on shifts in setting, characters, tone, narrative focus, or significant actions. Aim for frequent segmentation to capture subtle changes, ensuring each segment is a standalone visual unit.
                                    - **Generate Visual Descriptions**: For each segment, create a concise, vivid description ("visual_representation_of_text") capturing key visual elements like setting, characters, actions, and atmosphere.
                                    - **Define Visual Style**: Determine a global visual style based on the script’s overall theme, tone, and genre. Optionally, provide a style modifier for segments requiring distinct visual treatment.

                                    ## Input

                                    - A single string containing the full script.

                                    ## Output

                                    - A JSON object with:
                                        - `"segments"`: An array of objects, each containing:
                                            - `"text"`: The segment’s original text.
                                            - `"visual_representation_of_text"`: A vivid, concise visual description.
                                            - `"style_modifier"`: An optional style tweak (omit if not applicable).
                                        - `"script_scene_style"`: The global visual style applied to all segments unless modified.

                                    ## Guidelines

                                    *Note: Adapt these guidelines based on the script’s unique characteristics.*

                                    ### 1. Segmenting the Script

                                    Identify natural breaks where a new scene begins, prioritizing visual distinction. Consider segmenting at:
                                    - Changes in location or setting (e.g., indoors to outdoors).
                                    - Introduction, exit, or shift in focus of characters.
                                    - Time transitions (e.g., day to night).
                                    - Shifts in tone or mood (e.g., calm to tense).
                                    - Significant actions or events (e.g., a dramatic gesture).
                                    - Changes in narrative focus or new plot elements.

                                    For dialogue-heavy scenes:
                                    - Segment based on changes in speaker, tone, or significant actions/reactions.
                                    - Group rapid exchanges if they occur in the same context without visual shifts.

                                    ### 2. Generating Visual Descriptions

                                    Create a "visual_representation_of_text" for each segment that:
                                    - Is concise yet focusing on essential visual elements.
                                    - Uses descriptive language to paint a clear mental image.
                                    - Directly reflects the segment’s text and contributes to the narrative flow.
                                    - Includes sensory details like lighting, colors, textures, and spatial relationships.
                                    - It should be a Family friendly description.

                                    *Aim for descriptions detailed enough to guide image generation but not overly prescriptive.*

                                    ### 3. Determining Visual Style

                                    - **Global Style**: Analyze the script’s overarching theme, tone, or genre to select a detailed style (e.g., "hyper-realistic with muted tones and harsh lighting").
                                    - **Segment-Specific Style (Optional)**: Use concise modifiers (e.g., "sepia-toned") only when a segment’s context significantly differs from the global style.

                                    *Ensure the global style is keyword-rich and specific, while modifiers refine rather than replace it.*

                                    ## Additional Instructions

                                    - Each segment’s `"text"` should be a complete narrative or visual unit (typically 1-3 sentences). Split more frequently for subtle shifts to ensure visual variety.
                                    - If a sentence bridges scenes, place it in the segment where its primary action or change occurs.
                                    - Preserve original punctuation and sentence structure.
                                    - Balance segmentation to avoid incomplete fragments or merging unrelated moments.
                                    - List segments in their original order to maintain chronological sequence.
                                    - **Video Flow**: Ensure the sequence of segments and their visual descriptions creates a smooth narrative flow when viewed as a video. Pay attention to transitions between scenes to maintain coherence.
                                    - Use proper JSON syntax, omitting `"style_modifier"` if not applicable.

                                    ## Examples

                                    ### Example 1

                                    **Input:**

                                    "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids. At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away. She never made it home. The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat. But Linda was gone. The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street. She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument. With no signs of struggle and no immediate suspects, the case went cold."

                                    **Output:**

                                    ```json
                                    {
                                      "segments": [
                                        {
                                          "text": "It was a cold November evening in 1997 when 34-year-old Linda Calloway finished her shift at a small diner in downtown Milwaukee. She was a waitress, working late to support her two kids.",
                                          "visual_representation_of_text": "A small, retro-style diner glows faintly in the dark, its neon sign flickering. Linda, a tired but determined woman in her 30s, steps out, her uniform peeking from under her coat as she glances at her watch."
                                        },
                                        {
                                          "text": "At exactly 11:23 PM, security cameras caught her locking up the diner, wrapping her scarf tight against the chill, and walking toward her car parked a block away.",
                                          "visual_representation_of_text": "Grainy security footage shows Linda locking the diner’s glass door, her breath visible in the cold air. She wraps her scarf tighter and walks down the empty, dimly lit street toward her car parked under a flickering streetlamp."
                                        },
                                        {
                                          "text": "She never made it home.",
                                          "visual_representation_of_text": "A dark, empty street stretches out, with Linda’s footsteps echoing faintly. The camera pans to her house in the distance, its lights off, emphasizing her absence."
                                        },
                                        {
                                          "text": "The next morning, a jogger discovered her abandoned car on the side of a quiet residential street—unlocked, keys in the ignition, and her purse still in the front seat.",
                                          "visual_representation_of_text": "A serene suburban street bathed in morning light. A jogger stops abruptly, staring at Linda’s car: doors ajar, keys dangling, purse untouched on the seat, casting an unsettling contrast to the peaceful surroundings."
                                        },
                                        {
                                          "text": "But Linda was gone.",
                                          "visual_representation_of_text": "A close-up of the empty driver’s seat, the keys still in the ignition, and the faint outline of where Linda should be, emphasizing her mysterious disappearance."
                                        },
                                        {
                                          "text": "The investigation moved quickly. Police canvassed the area and found a witness—a retired schoolteacher who lived on that street.",
                                          "visual_representation_of_text": "Police officers knock on doors in the quiet neighborhood. An elderly woman, the schoolteacher, answers her door, her face a mix of curiosity and concern as she speaks to the officers."
                                        },
                                        {
                                          "text": "She recalled hearing a muffled scream around midnight but assumed it was just a late-night argument.",
                                          "visual_representation_of_text": "The schoolteacher sits in her cozy living room, a cup of tea in hand, her expression troubled as she recalls the scream. Through her window, the dark street is visible, with shadows stretching ominously.",
                                          "style_modifier": "eerie atmosphere with distorted shadows"
                                        },
                                        {
                                          "text": "With no signs of struggle and no immediate suspects, the case went cold.",
                                          "visual_representation_of_text": "A detective stands in front of a corkboard filled with photos and notes about Linda’s case, his face weary. The room is dimly lit, symbolizing the dead end in the investigation."
                                        }
                                      ],
                                      "script_scene_style": "hyper-realistic with muted tones and harsh lighting"
                                    }
                                    ```
                                    **Explanation:**
                                    - Segmentation: Eight segments capture distinct visual moments, from Linda’s diner exit to the investigation’s end.
                                    - Visual Descriptions: Each provides a clear, evocative image enhancing the narrative.
                                    - Global Style: "hyper-realistic with muted tones and harsh lighting" maintains a gritty mystery tone.
                                    - Modifier: Applied to the scream segment to heighten its eerie impact.
                                    ### Example 1

                                    **Input:**

                                    "The old house creaked as the wind howled outside. Inside, Sarah lit a candle and opened an ancient book. Shadows danced on the walls as she read aloud. Suddenly, the room grew cold, and a faint whisper echoed from the hallway."

                                    **Output:**
                                    ```json
                                    {
                                      "segments": [
                                        {
                                          "text": "The old house creaked as the wind howled outside.",
                                          "visual_representation_of_text": "An old, weathered house stands alone on a hill, its windows rattling as fierce winds whip around it, casting long, eerie shadows across the overgrown yard."
                                        },
                                        {
                                          "text": "Inside, Sarah lit a candle and opened an ancient book.",
                                          "visual_representation_of_text": "Sarah, a young woman with a curious expression, sits at a wooden table in a dimly lit room. She strikes a match, lighting a candle that illuminates the pages of a dusty, leather-bound book."
                                        },
                                        {
                                          "text": "Shadows danced on the walls as she read aloud.",
                                          "visual_representation_of_text": "The candlelight flickers, casting shifting shadows across the room’s peeling wallpaper. Sarah’s lips move as she reads, her voice barely audible over the wind outside."
                                        },
                                        {
                                          "text": "Suddenly, the room grew cold, and a faint whisper echoed from the hallway.",
                                          "visual_representation_of_text": "The room darkens as an unnatural chill sets in. Sarah looks up from the book, her breath visible, as a faint, ghostly whisper seems to emanate from the shadowy hallway beyond.",
                                          "style_modifier": "surreal with glowing edges"
                                        }
                                      ],
                                      "script_scene_style": "gothic with dark shadows and crimson accents"
                                    }
                                    ```
                                    **Explanation:**
                                    - Segmentation: Four segments highlight key actions and atmospheric shifts.
                                    - Visual Descriptions: Each builds tension progressively.
                                    - Global Style: "gothic with dark shadows and crimson accents" sets an eerie tone.
                                    - Modifier: "surreal with glowing edges" enhances the supernatural climax."""
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
