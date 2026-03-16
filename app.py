from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fittin-secret-key-change-in-production")

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"

# ── Emergency keywords ────────────────────────────────────────────────────────
EMERGENCY_KEYWORDS = [
    "chest pain", "chest tightness", "difficulty breathing", "can't breathe",
    "cannot breathe", "heavy bleeding", "loss of consciousness", "fainted",
    "unconscious", "not breathing", "heart attack", "stroke", "seizure",
]

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Fittin AI — a health awareness buddy made for high school students at SMA Kemala Taruna Bhayangkara.

---

## WHO YOU ARE
You're like a smart, caring older sibling (kakak) who happens to know a lot about health. You talk like a real person — warm, occasionally funny, never stiff. You make health feel approachable, not scary. Your information is always accurate and professional, but your delivery feels like a real conversation.

---

## LANGUAGE & WRITING RULES

**Simple words only, always.**
- NEVER use medical jargon without explaining it immediately after in simple words.
- BAD: "postnasal drip may be irritating your pharynx."
- GOOD: "your nose might be dripping mucus down the back of your throat (gross, but that's basically what happens with a cold 😅) — and that's probably what's making you cough."
- If you need a medical term, follow it immediately with "— basically, [plain explanation]."

**Write like you're talking, not reporting.**
- Short sentences. Line breaks between ideas. No walls of text.
- Vary your sentence length — mix short punchy lines with slightly longer ones.
- Use emojis naturally — they should feel like expressions, not decoration.

**Use emojis like a person, not a bot.**
- Sprinkle them naturally — roughly 1-3 per response, placed where they add warmth or emphasis.
- Good spots: after greetings 👋, at the end of a reassuring sentence 😊, next to a warning ⚠️, or when being a little playful 😅.
- Never start every bullet point with an emoji — that looks robotic.
- Never use more than one emoji in a row.
- Examples of natural use: "That sounds really uncomfortable 😬", "Good news — it's probably nothing serious 😊", "Three days is a while though ⚠️ — worth keeping an eye on."

**Match the user's energy.**
- Short message like "ok", "heyya", "thanks", "lol" → reply in 1-2 sentences MAX. Never write a paragraph back at someone who sent two words.
- Detailed symptom description → engage fully but keep it readable.
- Confused user → slow down, simplify even more.

---

## RESPONSE STYLES

### STYLE 1 — First Response (after the health form is submitted)
This is the opening analysis. Write it in a flowing, narrative style — NOT like a bullet-point report. It should feel like someone actually sat down and talked through the results with you.

**Format to follow:**

"Okay so, from the info you gave in the form, I can point out at least [number] possible things that might be going on with your [symptom] right now:

- **[Cause 1]** — [explain in simple, plain words why this could be the cause, 1-2 sentences]
- **[Cause 2]** — [same, plain and clear]
- **[Cause 3]** — [same]

Now, [write 2-3 sentences of context — why these causes make sense given their specific details like age, pain level, how long it's been going on. Keep it conversational, like you're connecting the dots for them, not reciting facts.]

[One more short paragraph] — mention 1-2 simple things they can try, written naturally. Not a list, just a sentence or two.

Just a heads up though — [ONE warning sign to watch for, kept calm and non-scary].

And of course, if things don't get better in a day or two, it's always worth checking in with a real doctor or your school's UKS, yeah? 🏥"

Then end with ONE natural follow-up question.

### STYLE 2 — Follow-Up Chat (every message after the first)
Fully conversational. This is a real back-and-forth now.

- Keep it SHORT — 2 to 4 short paragraphs at most
- If what they said is vague → ask ONE clarifying question first. Don't dump all causes at once.
- Only give a deeper analysis after you understand more
- Light humour totally welcome when the situation isn't serious
- No need for formal sections — just talk naturally
- End with a short doctor reminder ONLY if the situation calls for it

---

## HARD RULES — NEVER BREAK THESE

1. **NEVER diagnose.** Always "might be", "could be", "possibly", "sounds like."

2. **NEVER recommend specific doctors or clinics by name.** If someone asks where to find a doctor or hospital, respond warmly like this: "I can't name specific doctors, but you can easily find options near you on **Halodoc** (halodoc.com) or **Alodokter** (alodokter.com) — both let you search by location and specialty. Or just drop a search into Google Maps! I've also attached some search links below 👇" — then let the sources panel handle the actual links. Do NOT paste raw links or markdown links inside the chat text itself.

3. **NEVER name specific medicines or brands.** Say "a pain reliever" or "antihistamine" — never brand names or dosages.

4. **Short replies to short messages.** "ok", "okay", "heyya", "thanks", "lol" → MAX 2 sentences back. No paragraphs.

5. **Off-topic questions** (homework, games, politics, etc.): "Haha I appreciate the curiosity, but health is literally my whole personality! Ask me something body or wellness related 😄"

6. **ONE follow-up question per message.** Never stack questions.

7. **NEVER be alarmist** unless it's a genuine emergency.

8. **Always use the user's first name** if you know it.
"""

# ── Initial form prompt ────────────────────────────────────────────────────────
INITIAL_PROMPT_TEMPLATE = """A student just submitted their health check-in form. Here's their info:

👤 Name: {name}
🎂 Age: {age}
⚧ Gender: {gender}
🤒 Primary Symptom: {symptom}
📊 Pain Level: {pain_level}/10
📝 Notes: {notes}

Write a STYLE 1 response. Follow this structure exactly:

1. Start with: "Okay so, from the info you gave in the form, I can point out at least [X] possible things that might be going on with your [symptom] right now:"

2. List 3-4 possible causes as bullet points in this format:
   - **[Cause name]** — [plain, simple explanation of why this could be the cause. No jargon. If you must use a medical word, explain it immediately after.]

3. Write 2-3 sentences connecting the dots — reference their specific details (age, pain level, how long it's been, their notes). Make it feel personal, not generic.

4. In 1-2 casual sentences, mention something simple they can try.

5. ONE calm warning sign to watch for. Not scary — just informative.

6. End with the UKS/doctor reminder, kept light.

7. Then ask ONE natural follow-up question to keep the conversation going.

Remember: narrative and flowing, NOT a formatted report. Write like you're actually talking to them. Fun but professional.
"""


def is_emergency(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in EMERGENCY_KEYWORDS)


def build_initial_prompt(form_data: dict) -> str:
    return INITIAL_PROMPT_TEMPLATE.format(
        name       = form_data.get("name", "there"),
        age        = form_data.get("age", "unknown"),
        gender     = form_data.get("gender", "not specified"),
        symptom    = form_data.get("symptom", "unspecified"),
        pain_level = form_data.get("pain_level", "5"),
        notes      = form_data.get("notes", "None provided"),
    )


def build_form_summary(form_data: dict) -> str:
    lines = ["📋 Health Form Submission"]
    if form_data.get("name"):     lines.append(f"Name: {form_data['name']}")
    if form_data.get("age"):      lines.append(f"Age: {form_data['age']}")
    if form_data.get("gender"):   lines.append(f"Gender: {form_data['gender']}")
    if form_data.get("symptom"):  lines.append(f"Primary symptom: {form_data['symptom']}")
    lines.append(f"Pain level: {form_data.get('pain_level', '5')}/10")
    if form_data.get("notes"):    lines.append(f"Notes: {form_data['notes']}")
    return "\n".join(lines)


# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/form")
def form():
    return render_template("form.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    name       = request.form.get("name", "").strip()
    age        = request.form.get("age", "").strip()
    gender     = request.form.get("gender", "").strip()
    symptom    = request.form.get("symptom", "").strip()
    pain_level = request.form.get("pain_level", "5").strip()
    notes      = request.form.get("notes", "").strip()

    # Emergency check
    if is_emergency(symptom) or is_emergency(notes):
        session["initial_message"] = (
            "⚠️ This sounds like it could be a medical emergency. "
            "Please get help from a trusted adult, doctor, or the nearest hospital right away. "
            "Don't wait on this one — your safety comes first! 🏥"
        )
        session["form_summary"] = None
        session["raw_prompt"]   = None
        session["chat_history"] = []
        return redirect(url_for("chat"))

    form_data = {
        "name": name, "age": age, "gender": gender,
        "symptom": symptom, "pain_level": pain_level, "notes": notes,
    }

    prompt       = build_initial_prompt(form_data)
    form_summary = build_form_summary(form_data)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=800,
            temperature=0.85,  # slightly higher = more personality
        )
        ai_reply = response.choices[0].message.content
    except Exception as e:
        ai_reply = f"⚠️ Oops, something went wrong on my end! Error: {str(e)}"

    session["initial_message"] = ai_reply
    session["form_summary"]    = form_summary
    session["raw_prompt"]      = prompt
    session["chat_history"]    = [
        {"role": "user",      "content": prompt},
        {"role": "assistant", "content": ai_reply},
    ]
    session["user_name"] = name

    return redirect(url_for("chat"))


@app.route("/chat")
def chat():
    return render_template(
        "chat.html",
        initial_message = session.get("initial_message", None),
        form_summary    = session.get("form_summary", None),
        raw_prompt      = session.get("raw_prompt", None),
    )


@app.route("/chat", methods=["POST"])
def chat_api():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided."}), 400

    latest = messages[-1].get("content", "")
    if is_emergency(latest):
        return jsonify({
            "reply": (
                "⚠️ Hey, this sounds serious. Please reach out to a doctor, trusted adult, "
                "or head to the nearest hospital right away. Your health comes first! 🏥"
            )
        })

    try:
        groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        response = client.chat.completions.create(
            model=MODEL,
            messages=groq_messages,
            max_tokens=800,
            temperature=0.85,
        )
        return jsonify({"reply": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500


@app.route("/new-chat", methods=["POST"])
def new_chat():
    session.pop("initial_message", None)
    session.pop("form_summary", None)
    session.pop("raw_prompt", None)
    session.pop("chat_history", None)
    return jsonify({"status": "ok"})


# ── Detect query type ─────────────────────────────────────────────────────────
import re

DOCTOR_PATTERNS = [
    r'\bdoctor\b', r'\bdokter\b', r'\bhospital\b', r'\brumah sakit\b',
    r'\bclinic\b', r'\bklinik\b', r'\bnearest\b', r'\bterdekat\b',
    r'\bwhere.*go\b', r'\bwhere.*find\b', r'\bpuskesmas\b',
]
SERIOUS_PATTERNS = [
    r'\bcancer\b', r'\btumor\b', r'\bstroke\b', r'\bheart attack\b',
    r'\bappendix\b', r'\bappendicit\b', r'\bmeningitis\b', r'\bdiabetes\b',
    r'\bchronic\b', r'\bserious\b', r'\bsevere\b',
]

def is_doctor_query(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in DOCTOR_PATTERNS)

def is_serious_query(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in SERIOUS_PATTERNS)


@app.route("/chat-enhanced", methods=["POST"])
def chat_enhanced():
    """
    Enhanced chat that:
    - For doctor/hospital queries: generates Google Maps search link + nearby options
    - For serious symptoms: searches for reliable medical sources (journals/hospitals)
    - Returns { reply, sources: [{title, url}] }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    messages = data.get("messages", [])
    query    = data.get("query", "")

    if not messages:
        return jsonify({"error": "No messages provided."}), 400

    latest = messages[-1].get("content", query)

    # Emergency check
    if is_emergency(latest):
        return jsonify({
            "reply": (
                "⚠️ Hey, this sounds serious. Please reach out to a doctor, trusted adult, "
                "or head to the nearest hospital right away. Your health comes first! 🏥"
            ),
            "sources": []
        })

    sources = []

    # ── Doctor/Hospital query → generate Google Maps links ───────────────────
    if is_doctor_query(latest):
        # Extract location hint from the query
        loc_match = re.search(
            r'\bin\s+([\w\s]+?)(?:\?|$|\.|\bfor\b|\bwith\b|\bthat\b)',
            latest, re.IGNORECASE
        )
        location = loc_match.group(1).strip() if loc_match else "Yogyakarta"

        # Build Google Maps search URLs
        maps_base = "https://www.google.com/maps/search/"
        import urllib.parse

        def maps_url(q):
            return maps_base + urllib.parse.quote(q)

        # Determine what type of facility they're looking for
        if re.search(r'\bdentist\b|\bgigi\b', latest, re.I):
            search_terms = [
                ("Dentist near " + location,         maps_url(f"dentist near {location}")),
                ("Dental clinic " + location,        maps_url(f"klinik gigi {location}")),
            ]
        elif re.search(r'\bhospital\b|\brumah sakit\b', latest, re.I):
            search_terms = [
                ("Hospitals near " + location,       maps_url(f"hospital near {location}")),
                ("Rumah Sakit " + location,          maps_url(f"rumah sakit {location}")),
            ]
        elif re.search(r'\bpuskesmas\b', latest, re.I):
            search_terms = [
                ("Puskesmas near " + location,       maps_url(f"puskesmas near {location}")),
            ]
        else:
            search_terms = [
                ("Doctors near " + location,         maps_url(f"doctor near {location}")),
                ("Clinics near " + location,         maps_url(f"clinic near {location}")),
                ("Puskesmas near " + location,       maps_url(f"puskesmas {location}")),
            ]

        sources = [{"title": title, "url": url} for title, url in search_terms]

        # Modify the prompt to mention we're providing map links
        map_note = (
            f"\n\nIMPORTANT instruction for your response: "
            f"Do NOT paste any URLs or markdown links inside your reply text. "
            f"Just tell the user warmly that you can't name specific places, "
            f"suggest they check Halodoc (halodoc.com) or Alodokter (alodokter.com) by name only, "
            f"and mention that Google Maps search links have been attached below. "
            f"Keep it short, friendly, and helpful. Location context: {location}."
        )
        messages = messages[:-1] + [{"role": "user", "content": latest + map_note}]

    # ── Serious symptom query → find reliable medical sources ────────────────
    elif is_serious_query(latest):
        # Extract the main condition keyword for source building
        condition_map = {
            'cancer':       ('cancer',       'cancer.gov',      'https://www.cancer.gov/about-cancer/understanding/what-is-cancer'),
            'tumor':        ('tumor',        'cancer.gov',      'https://www.cancer.gov/about-cancer/understanding/what-is-cancer'),
            'diabetes':     ('diabetes',     'diabetes.org',    'https://www.diabetes.org/diabetes'),
            'heart attack': ('heart attack', 'heart.org',       'https://www.heart.org/en/health-topics/heart-attack/about-heart-attacks'),
            'stroke':       ('stroke',       'stroke.org',      'https://www.stroke.org/en/about-stroke/what-is-a-stroke'),
            'appendicit':   ('appendicitis', 'hopkinsmedicine', 'https://www.hopkinsmedicine.org/health/conditions-and-diseases/appendicitis'),
            'meningitis':   ('meningitis',   'cdc.gov',         'https://www.cdc.gov/meningitis/index.html'),
            'chronic':      ('chronic pain', 'mayoclinic.org',  'https://www.mayoclinic.org/diseases-conditions/chronic-pain/symptoms-causes/syc-20350823'),
        }
        t = latest.lower()
        for keyword, (label, domain, url) in condition_map.items():
            if keyword in t:
                sources.append({"title": f"About {label.title()} — {domain}", "url": url})

        # Always add a Google Scholar search for the symptom
        words = re.findall(r'\b\w{4,}\b', latest)
        scholar_q = '+'.join(words[:4]) if words else 'health+symptoms'
        sources.append({
            "title": "Search Google Scholar for research",
            "url":   f"https://scholar.google.com/scholar?q={scholar_q}"
        })

        note = (
            "\n\nNote: The user is asking about a potentially serious health condition. "
            "In your response, gently acknowledge it might be worth getting checked professionally. "
            "You've attached reliable reference links below."
        )
        messages = messages[:-1] + [{"role": "user", "content": latest + note}]

    # ── Call Groq ─────────────────────────────────────────────────────────────
    try:
        groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        response = client.chat.completions.create(
            model=MODEL,
            messages=groq_messages,
            max_tokens=800,
            temperature=0.85,
        )
        return jsonify({
            "reply":   response.choices[0].message.content,
            "sources": sources
        })
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
