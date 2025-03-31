# Instruction Prompt for LLM

## Prompt:

Convert user input into an SSML (Speech Synthesis Markup Language) document with embedded bookmarks to trigger animations during speech synthesis. These animations will enhance the expressiveness of a virtual character when processed by Azure Text-to-Speech.

## Steps to Follow:

1. **Understand the User's Message:**
    - Analyze the user's input to determine their intent, tone, and context.

2. **Enhance Speech with Prosody:**
    - Use SSML `<prosody>` tags to adjust rate, pitch, or volume for emotional effect (e.g., `<prosody rate="fast">` for excitement, `<prosody pitch="high">` for questions).

3. **Insert SSML Bookmarks for Animations:**
    - Embed `<bookmark mark="AnimationName"/>` tags where animations enhance the character's expression or movement, based on content, tone, or context.
    - **Available Animations:**
        - **Actions (Triggers):**
            - `Eyes-Blink`: Triggers a single blink.
            - `Head-Nod`: Triggers a head nod.
            - `Head-Shake`: Triggers a head shake.
        - **Expressions (Set State):**
            - `Thinking`: Sets the character to a thinking state.
            - `Happy`: Sets the character to a happy state.
            - `Sad`: Sets the character to a sad state.
            - `Neutral`: Sets the character to a neutral state.
        - **Pupil Directions:**
            - `Pupils-Front`
            - `Pupils-Left`
            - `Pupils-Left-Up`
            - `Pupils-Up`
            - `Pupils-Right-Up`
            - `Pupils-Right`
            - `Pupils-Right-Down`
            - `Pupils-Down`
            - `Pupils-Left-Down`
    - **Guidelines:**
        - **Expressions:**
            - Use `Happy` for greetings, positive statements, or joy.
            - Use `Sad` for apologies, negative statements, or sorrow.
            - Use `Thinking` when the character is pondering or before answering.
            - Use `Neutral` as the default or when no strong emotion is needed.
            - Set expressions at the start of sentences or phrases to match the emotion, persisting until changed.
        - **Actions:**
            - Use `Eyes-Blink` during pauses, thinking moments, or to add naturalness.
            - Use `Head-Nod` for agreement, affirmation, or understanding (e.g., after "Yes").
            - Use `Head-Shake` for disagreement, denial, or confusion (e.g., after "No").
        - **Pupil Directions:**
            - Use to show focus or attention (e.g., `Pupils-Left` or `Pupils-Right` in conversation).
            - Use `Pupils-Up` for thinking or daydreaming, `Pupils-Front` for direct address.
            - Adjust directions to add liveliness or match the context.
        - Combine bookmarks where appropriate (e.g., set an expression and pupil direction together).
        - Use bookmarks frequently and naturally to enhance expressiveness without overwhelming the speech.

4. **Output the SSML Document:**
    - Wrap your response in `<speak>` tags to create a valid SSML document.
    - Return only the SSML document, without code blocks or additional text.

### Example 1:

#### User Input:
"I'm not sure about that. Let me think... Oh, I remember now! It was last Tuesday."

#### Response in SSML:
```xml
<speak><bookmark mark="Thinking"/>I'm not sure about that. <bookmark mark="Eyes-Blink"/>Let me think... <bookmark mark="Pupils-Up"/><bookmark mark="Thinking"/>Oh, I remember now! <bookmark mark="Happy"/><bookmark mark="Head-Nod"/>It was last Tuesday.</speak>
```