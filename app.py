from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import openai
import json
import os
import re
import logging
import html
from google import genai
from google.genai import types
import azure.cognitiveservices.speech as speechsdk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Enable CORS for all routes, allowing requests from your frontend
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173", "https://ai-anime-dating.onrender.com"]}})
system_instruction_split_context="""# Video Segmentation Instruction Prompt

                                    Transform scripts into fluid video sequences by creating highly granular visual segments with consistent character design.

                                    ## Core Principle: Visual Focus Hierarchy

                                    **Each segment describes what dominates the frame visually.**

                                    ### Decision Rule for Every Segment:

                                    **Ask: "What's the primary visual element in this shot?"**

                                    1. **Character emotion/reaction** → Describe character fully with exact physical features
                                    2. **Character performing major action** → Describe character fully
                                    3. **Environmental effect/object** → Describe environment only (no character mention)
                                    4. **Setting/atmosphere** → Describe setting only (no character mention)

                                    **Key**: Characters can be present without being described. Only describe them when they're the visual subject.

                                    ---

                                    ## Output Format

                                    ```json
                                    {
                                      "script_scene_style": "Style description + complete character definitions",
                                      "segments": [
                                        {
                                          "text": "Original script text (1-2 sentences)",
                                          "visual_representation_of_text": "Visual description focused on primary element",
                                          "style_modifier": "Optional style variation"
                                        }
                                      ]
                                    }
                                    ```

                                    ---

                                    ## 1. Character Consistency

                                    ### Define Characters Once
                                    In `script_scene_style`, include complete character definitions:
                                    ```
                                    "Playful cartoon style featuring Pip (kid with messy brown hair, big round glasses,
                                    colorful striped sweater, curious personality) and Luna (girl with long purple braids,
                                    yellow raincoat, green eyes, adventurous personality)"
                                    ```

                                    ### Use Characters Correctly
                                    - **When character IS visual focus**: Use full description with exact features
                                      - ✅ "Pip's big round glasses sparkle with excitement, messy brown hair bouncing"

                                    - **When environment IS visual focus**: Skip character description entirely
                                      - ✅ "Rainbow colors twirl and dance across the computer screen"
                                      - ❌ "Rainbow colors twirl across the screen in front of Pip (kid with messy brown hair...)"

                                    ### Never Change Appearance
                                    When you describe a character, always use identical physical features:
                                    - Same hair color, style, and length
                                    - Same eye color
                                    - Same clothing and accessories
                                    - Same distinctive features

                                    ---

                                    ## 2. Segmentation Rules

                                    ### Create 2-3x More Segments Than Expected

                                    **Segment at every:**
                                    - Action change (each distinct movement)
                                    - Visual focus shift (character → object → environment)
                                    - Emotional reaction (each expression change)
                                    - Camera angle change (close-up → wide shot)

                                    ### Length Guidelines
                                    - **Target**: 1-2 sentences per segment
                                    - **Split multi-action sentences** into separate segments
                                    - Think: Each segment = one 3-5 second camera shot

                                    ### Example Segmentation:

                                    **❌ Too Few (1 segment):**
                                    ```
                                    "Mia walked through the forest, pushed branches aside, and saw a glowing cabin."
                                    ```

                                    **✅ Correct (3 segments):**
                                    ```
                                    Segment 1: "Mia walked through the forest,"
                                    → Mia walks between tall trees, feet crunching on colorful leaves

                                    Segment 2: "pushed branches aside,"
                                    → Close-up of hands gently moving wiggly branches apart

                                    Segment 3: "and saw a glowing cabin."
                                    → Mia's eyes widen with surprise seeing a cozy cabin with twinkly lights
                                    ```

                                    ---

                                    ## 3. Visual Descriptions (Child-Friendly Language)

                                    ### Always Use Simple, Playful Words

                                    **✅ Use:**
                                    - Bright colors, rainbow colors, pretty lights
                                    - Fun patterns, happy designs, colorful swirls
                                    - Playful shapes, cute drawings
                                    - Twirling, spinning, dancing, bouncing
                                    - Happy sparkles, twinkly glow, magical shine

                                    **❌ Never Use:**
                                    - Neon, psychedelic, abstract, intense
                                    - Dark, mysterious, sensual, provocative
                                    - Swirling, avant-garde, expressionist, surreal

                                    ### Focus on ONE Visual Element
                                    Each description should spotlight a single primary element:
                                    - Character close-up
                                    - Environmental effect
                                    - Object detail
                                    - Action moment

                                    ---

                                    ## 4. Complete Example

                                    ### Input Script:
                                    "Pip sat at the computer, eyes wide. The screen exploded with code. Colorful pumpkins appeared. Pip laughed with joy."

                                    ### Output:

                                    ```json
                                    {
                                      "script_scene_style": "Playful cartoon style featuring Pip (kid with messy brown hair, big round glasses, colorful striped sweater, curious personality) in a magical computer world",
                                      "segments": [
                                        {
                                          "text": "Pip sat at the computer, eyes wide.",
                                          "visual_representation_of_text": "Pip sits at a desk with messy brown hair, big round glasses reflecting the screen, wearing a colorful striped sweater, eyes sparkling with wonder"
                                        },
                                        {
                                          "text": "The screen exploded with code.",
                                          "visual_representation_of_text": "Bright colorful lines of code pop and bounce all over the computer screen like happy fireworks"
                                        },
                                        {
                                          "text": "Colorful pumpkins appeared.",
                                          "visual_representation_of_text": "Little pumpkin drawings with smiley faces bounce up all over the screen with fun patterns"
                                        },
                                        {
                                          "text": "Pip laughed with joy.",
                                          "visual_representation_of_text": "Pip giggles happily, messy brown hair bouncing, big round glasses catching the magical screen light, colorful striped sweater bright and cheerful"
                                        }
                                      ]
                                    }
                                    ```

                                    **Notice:**
                                    - Segments 1 & 4: Character is focus → Full descriptions used
                                    - Segments 2 & 3: Screen/objects are focus → No character descriptions
                                    - Character appearance identical in segments 1 & 4
                                    - All language child-friendly and playful

                                    ---

                                    ## 5. Quality Checklist

                                    Before submitting, verify:

                                    - [ ] **Visual Focus**: Does each segment describe only the primary visual element?
                                    - [ ] **Character Usage**: Are characters described only when they're the visual subject?
                                    - [ ] **Character Consistency**: When characters ARE described, do they have identical features?
                                    - [ ] **Segment Frequency**: Do you have 2-3x more segments than paragraphs?
                                    - [ ] **Child-Friendly**: All descriptions use simple, playful, innocent language?
                                    - [ ] **Smooth Flow**: Does each segment naturally lead to the next?

                                    ---

                                    ## Key Reminders

                                    **Visual hierarchy over constant presence**: Show what dominates each frame.

                                    **Character consistency when shown**: Same appearance every time, but not in every segment.

                                    **Segment frequently**: More segments = smoother video flow.

                                    **Think like a camera**: Each segment is one shot in a children's cartoon.

                                    **Stay playful**: Pretty colors, happy sparkles, bouncy movements, cute drawings."""
system_instruction_directResponse="""# Instruction Prompt for LLM

                                     ## Prompt:

                                     Convert the ENTIRE user input text (including any titles, headings, or narrative content) into an SSML (Speech Synthesis Markup Language) document with embedded bookmarks to trigger animations during speech synthesis. These animations will enhance the expressiveness of a virtual character when processed by Azure Text-to-Speech.

                                     ### Steps to Follow:

                                     - **Process the Complete Input:**

                                         - Include ALL text from the user input, including titles, headings, and narrative content. Do not skip or omit any part of the input.
                                         - Analyze the complete text to determine appropriate tone, context, and emotional content for animation placement.

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
    try:
        logger.info("Received request to /api/respond")
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid Request", "details": "No JSON data provided", "api": "Request Parsing"}), 400

        message = data.get("message")
        if not message:
            return jsonify({"error": "Invalid Request", "details": "No message provided", "api": "Request Parsing"}), 400

        personality = data.get("personality", "cheerful")
        degree = data.get("styledegree", "1")
        getAiResponse = data.get("getAiResponse", True)
        getScriptContext = data.get("getScriptContext", True)
        logger.info(f"Processing request with personality: {personality}, getAiResponse: {getAiResponse}, getScriptContext: {getScriptContext}")

        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        aiResponse = ""
        splitContext = ""
        question = "User Input:\n"
        question += message

        # Handle script context generation with error handling
        if(getScriptContext):
            try:
                logger.info("Generating script context with Gemini API")
                splitContext = client.models.generate_content(
                                model="gemini-2.0-flash",
                                config=types.GenerateContentConfig(
                                    system_instruction=system_instruction_split_context), #using the Split context instruction here
                                    #Add temprature for variability
                                contents=[question] #send the user input
                    )
                logger.info("Successfully generated script context")
            except Exception as e:
                logger.error(f"Failed to generate script context with Gemini API: {str(e)}")
                return jsonify({
                    "error": "Script Context Generation Failed",
                    "details": f"Gemini API call for script context failed: {str(e)}",
                    "api": "Google Gemini (Script Context)"
                }), 500
        question += "\n Please generate the SSML-enhanced text based on this input."

        # Handle AI response generation with error handling
        if(getAiResponse):
            try:
                logger.info("Generating AI response with Gemini API (full response)")
                aiResponse = client.models.generate_content(
                        model="gemini-2.0-flash",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction), #using the SSML instructions prompt here
                            #Add temprature for variability
                        contents=[question] #send the user input
                    )
                logger.info("Successfully generated AI response")
            except Exception as e:
                logger.error(f"Failed to generate AI response with Gemini API: {str(e)}")
                return jsonify({
                    "error": "AI Response Generation Failed",
                    "details": f"Gemini API call for AI response failed: {str(e)}",
                    "api": "Google Gemini (AI Response)"
                }), 500
        else:
            try:
                logger.info("Generating direct AI response with Gemini API (SSML only)")
                aiResponse = client.models.generate_content(
                        model="gemini-2.0-flash",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction_directResponse), #using the SSML instructions prompt here
                            #Add temprature for variability
                        contents=[question] #send the user input
                    )
                logger.info("Successfully generated direct AI response")
            except Exception as e:
                logger.error(f"Failed to generate direct AI response with Gemini API: {str(e)}")
                return jsonify({
                    "error": "Direct AI Response Generation Failed",
                    "details": f"Gemini API call for direct response failed: {str(e)}",
                    "api": "Google Gemini (Direct Response)"
                }), 500
        def convert_response_to_list(input_json):
            try:
                logger.info("Parsing script context JSON response")
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
                logger.info(f"Successfully parsed {len(segments)} segments with style: {style}")
                return segments, style  # Return both as a tuple
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for script context: {str(e)}")
                logger.error(f"Raw input: {input_json[:500]}...")  # Log first 500 chars for debugging
                return [], 'realistic'  # Return defaults on error
            except Exception as e:
                logger.error(f"Unexpected error parsing script context: {str(e)}")
                return [], 'realistic'  # Return defaults on error

        # Usage
        outputImagePrompts = convert_response_to_list(splitContext.text)
        segments, style = outputImagePrompts  # Unpack the tuple
        #AZURE LOGIC:  Set up speech configuration
        try:
            logger.info("Setting up Azure Speech Synthesis configuration")
            subscription_key = os.environ.get("AZURE_API_KEY")
            if not subscription_key:
                raise ValueError("AZURE_API_KEY environment variable not set")

            region = "canadacentral"
            speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
            speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"

            # Create speech synthesizer
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            logger.info("Successfully configured Azure Speech Synthesis")
        except Exception as e:
            logger.error(f"Failed to configure Azure Speech Synthesis: {str(e)}")
            return jsonify({
                "error": "Azure Speech Synthesis Configuration Failed",
                "details": f"Failed to set up Azure speech configuration: {str(e)}",
                "api": "Azure Speech Synthesis (Configuration)"
            }), 500

        # Initialize list to collect viseme and word timing events
        events = []

        def viseme_handler(evt):
            offset_ms = evt.audio_offset / 10000  # Convert ticks to milliseconds
            events.append({
                "time": offset_ms,
                "type": "viseme",
                "value": evt.viseme_id
            })
        def clean_word_text(word):
            """Clean word text to remove SSML artifacts and formatting"""
            try:
                # Decode HTML entities first
                cleaned = html.unescape(word)
                # Remove common SSML/formatting artifacts
                cleaned = cleaned.replace('>', '').replace('\n', '').replace('\t', '').replace('\r', '')
                # Remove any remaining XML tags that might leak through
                cleaned = re.sub(r'<[^>]+>', '', cleaned)
                # Strip whitespace
                return cleaned.strip()
            except Exception:
                # Fallback to original word if cleaning fails
                return word.strip()

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
        try:
            logger.info("Starting Azure Speech Synthesis")
            textValue = aiResponse.text.strip()
            if textValue.startswith('```xml\n'):
                textValue = textValue.split('\n', 1)[1].rsplit('\n', 1)[0]

            # Decode HTML entities to ensure word timings align with clean text
            textValue = html.unescape(textValue)

            # Ensure proper SSML header
            if not textValue.startswith('<speak version='):
                #https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts#voice-styles-and-roles
                textValue = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US"><voice name="en-US-AriaNeural"><mstts:express-as style="' + personality + '" styledegree="' + degree + '">' + textValue[7:-8] + '</mstts:express-as></voice></speak>'

            logger.info("Sending SSML to Azure Speech Synthesis API")
            result = synthesizer.speak_ssml_async(textValue).get() #speak_ssml_async or speak_text_async
            logger.info("Speech synthesis completed")
        except Exception as e:
            logger.error(f"Failed during Azure Speech Synthesis: {str(e)}")
            return jsonify({
                "error": "Azure Speech Synthesis Failed",
                "details": f"Speech synthesis API call failed: {str(e)}",
                "api": "Azure Speech Synthesis (Synthesis)"
            }), 500
        # Check synthesis result and retrieve audio and timings
        try:
            logger.info("Processing Azure Speech Synthesis results")
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info("Speech synthesis completed successfully, processing results")
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
                        "word": clean_word_text(e["word"])  # Clean word text of SSML artifacts
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

                logger.info("Successfully processed all synthesis results")
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
                logger.error(f"Azure Speech Synthesis failed with reason: {result.reason}")
                error_message = f"Synthesis failed with reason: {result.reason}"
                if result.reason == speechsdk.ResultReason.Canceled:
                    cancellation_details = speechsdk.SpeechSynthesisCancellationDetails(result)
                    error_message += f", ErrorCode: {cancellation_details.error_code}, Details: {cancellation_details.error_details}"
                    logger.error(f"Synthesis cancellation details: {cancellation_details.error_details}")
                return jsonify({
                    "error": "Azure Speech Synthesis Failed",
                    "details": error_message,
                    "api": "Azure Speech Synthesis (Result Processing)"
                }), 500
        except Exception as e:
            logger.error(f"Failed to process Azure Speech Synthesis results: {str(e)}")
            return jsonify({
                "error": "Azure Speech Synthesis Result Processing Failed",
                "details": f"Failed to process synthesis results: {str(e)}",
                "api": "Azure Speech Synthesis (Result Processing)"
            }), 500

    except Exception as e:
        logger.error(f"Unexpected error in /api/respond endpoint: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Internal Server Error",
            "details": f"An unexpected error occurred: {str(e)}",
            "api": "General Error Handler"
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT env var
    app.run(host="0.0.0.0", port=port)
