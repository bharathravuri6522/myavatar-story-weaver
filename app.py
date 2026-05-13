import streamlit as st
from dotenv import load_dotenv
from groq import Groq
import os
import json
import re

load_dotenv()

st.set_page_config(page_title="MyAvatar Story Weaver", page_icon="📖", layout="wide")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ====================== STRONG SYSTEM PROMPT ======================
SYSTEM_PROMPT = """You are a masterful collaborative storyteller.
You must maintain PERFECT consistency with:
- All characters (names, personalities, backstories, development)
- Established plot events and world rules
- The chosen genre, tone, and style

Rules:
- Write in vivid, immersive third-person narrative.
- Keep paragraphs concise (2-4 sentences each).
- Always advance the plot naturally.
- Never contradict previous events.
- Never summarize or break character."""

# ====================== SESSION STATE ======================
if "story_history" not in st.session_state:
    st.session_state.story_history = []
if "title" not in st.session_state:
    st.session_state.title = ""
if "genre" not in st.session_state:
    st.session_state.genre = "Fantasy"
if "initial_hook" not in st.session_state:
    st.session_state.initial_hook = ""
if "characters" not in st.session_state:
    st.session_state.characters = {}
if "choices" not in st.session_state:
    st.session_state.choices = None

# ====================== HELPERS ======================
def get_full_context() -> str:
    lines = [
        f"Title: {st.session_state.title}",
        f"Genre: {st.session_state.genre}",
        f"Initial Hook: {st.session_state.initial_hook}",
        "",
        "Story so far:",
    ]
    for entry in st.session_state.story_history:
        role = "User" if entry["role"] == "user" else "AI"
        lines.append(f"\n{role}:\n{entry['content']}")
    return "\n".join(lines)


def call_llm(prompt: str, temperature: float | None = None) -> str | None:
    if temperature is None:
        temperature = st.session_state.get("temperature_slider", 0.85)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",   # Lighter model with higher daily limits
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=700,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "rate limit" in err:
            if "daily" in err or "quota" in err:
                st.error("🚫 Daily quota exhausted. Please come back tomorrow.")
            else:
                st.warning("⏳ Rate limit reached. Please wait 10–30 seconds and try again.")
        else:
            st.error(f"LLM Error: {e}")
        return None


def call_llm_json(prompt: str, temperature: float = 0.2) -> dict | None:
    raw = call_llm(prompt, temperature=temperature)
    if not raw:
        return None

    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        st.warning("⚠️ Failed to parse character data.")
        return None


def extract_characters() -> None:
    if not st.session_state.story_history:
        return

    context = get_full_context()
    prompt = f"""{context}

**CRITICAL TASK**: Extract EVERY named character mentioned in the entire story so far.
Include heroes, villains, mentors, allies — anyone with a name.

Return ONLY valid JSON:

{{
  "characters": [
    {{
      "name": "Full Name",
      "description": "One sentence: role and key personality traits.",
      "arc": "Current status or recent development."
    }}
  ]
}}"""

    data = call_llm_json(prompt, temperature=0.1)
    if data and isinstance(data.get("characters"), list):
        st.session_state.characters = {
            char["name"]: char
            for char in data["characters"]
            if isinstance(char, dict) and "name" in char
        }


# ====================== UI ======================
st.title("📖 MyAvatar Story Weaver")
st.caption("AI-Powered Collaborative Storytelling • Llama 3.1 8B")

with st.sidebar:
    st.header("🎛️ Controls")
    st.slider("Temperature (Creativity)", 0.0, 1.0, 0.85, 0.05, key="temperature_slider")
    st.caption("**Lower = More consistency & logical flow** | **Higher = More creativity & surprising twists**")

    st.divider()
    st.header("👥 Live Characters")
    if st.session_state.characters:
        for name, info in st.session_state.characters.items():
            with st.expander(f"**{name}**"):
                st.write(info.get("description", "No description."))
                if info.get("arc"):
                    st.caption(f"**Arc:** {info['arc']}")
    else:
        st.caption("Characters will appear here after AI responses.")

    st.divider()
    if st.button("🔄 Start New Story", type="secondary", use_container_width=True):
        for key in ["story_history", "characters", "title", "initial_hook", "choices"]:
            st.session_state[key] = [] if key == "story_history" else {} if key == "characters" else None
        st.rerun()

# ====================== STORY SETUP ======================
if not st.session_state.title:
    st.header("1. Start a New Story")
    title = st.text_input("Story Title", placeholder="Indian version of Power Rangers")
    genre = st.selectbox("Genre", ["Fantasy", "Sci-Fi", "Mystery", "Romance", "Horror", "Comedy"])
    hook = st.text_area("Initial Hook / Setting", height=120,
                        placeholder="Describe the world, conflict, and main characters...")

    if st.button("🚀 Start the Story", type="primary", use_container_width=True):
        if title.strip() and hook.strip():
            st.session_state.title = title.strip()
            st.session_state.genre = genre
            st.session_state.initial_hook = hook.strip()

            with st.spinner("Writing opening paragraph..."):
                opening_prompt = f"Title: {title}\nGenre: {genre}\nHook: {hook}\n\nWrite a strong 150–250 word opening paragraph."
                opening = call_llm(opening_prompt)
                if opening:
                    st.session_state.story_history.append({"role": "ai", "content": opening})
                    extract_characters()
                    st.rerun()
        else:
            st.warning("Please fill in both Title and Initial Hook.")

# ====================== MAIN STORY VIEW ======================
else:
    st.header(f"📜 {st.session_state.title}")
    st.caption(f"**Genre:** {st.session_state.genre}")

    for entry in st.session_state.story_history:
        if entry["role"] == "ai":
            st.markdown(f"**🤖 AI**")
            st.markdown(entry["content"])
        else:
            st.markdown(f"**🧑 You**")
            st.markdown(f"> {entry['content']}")
        st.divider()

    input_key = f"user_input_{len(st.session_state.story_history)}"
    user_input = st.text_area(
        "Your contribution (optional — leave blank for pure AI continuation)",
        height=120,
        key=input_key,
        placeholder="Add dialogue, action, or plot twist..."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✍️ Continue with AI", type="primary", use_container_width=True):
            text = user_input.strip()
            if text:
                st.session_state.story_history.append({"role": "user", "content": text})

            with st.spinner("AI is continuing the story..."):
                context = get_full_context()
                continuation = call_llm(f"{context}\n\nContinue naturally with 1–2 vivid paragraphs.")
                if continuation:
                    st.session_state.story_history.append({"role": "ai", "content": continuation})
                    extract_characters()
            
            st.rerun()

    with col2:
        if st.button("🔀 Give Me 3 Choices", use_container_width=True):
            text = user_input.strip()
            if text:
                st.session_state.story_history.append({"role": "user", "content": text})

            with st.spinner("Generating choices..."):
                context = get_full_context()
                choices_text = call_llm(f"{context}\n\nSuggest exactly 3 interesting directions. Number them 1, 2, 3.")
                if choices_text:
                    st.session_state.choices = choices_text
            st.rerun()

    # Choices Handler
    if st.session_state.choices:
        st.subheader("🔀 Choose your path:")
        lines = [l.strip() for l in st.session_state.choices.split("\n") if l.strip() and l.strip()[0].isdigit()]
        for i, line in enumerate(lines):
            if st.button(line, key=f"choice_{i}", use_container_width=True):
                st.session_state.story_history.append({"role": "user", "content": line})
                st.session_state.choices = None
                with st.spinner("Continuing..."):
                    context = get_full_context()
                    cont = call_llm(f"{context}\n\nContinue the story naturally.")
                    if cont:
                        st.session_state.story_history.append({"role": "ai", "content": cont})
                        extract_characters()
                        st.rerun()

    st.divider()

    # Genre Remix
    st.subheader("🎭 Genre Remix")
    genres = ["Fantasy", "Sci-Fi", "Mystery", "Romance", "Horror", "Comedy"]
    new_genre = st.selectbox("Remix latest section into:", genres, 
                           index=genres.index(st.session_state.genre), key="remix_genre_select")
    if st.button("Apply Remix", type="primary", use_container_width=True):
        with st.spinner(f"Remixing into {new_genre}..."):
            context = get_full_context()
            remixed = call_llm(f"{context}\n\nRewrite the most recent AI paragraph in the genre: {new_genre}. Keep ALL characters and plot the same.")
            if remixed:
                st.session_state.genre = new_genre
                st.session_state.story_history.append({"role": "ai", "content": f"[Genre Remix → {new_genre}]\n\n{remixed}"})
                extract_characters()
                st.rerun()

    st.divider()

    # Bonus Features Row
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("↩️ Undo Last AI Turn", use_container_width=True):
            if st.session_state.story_history and st.session_state.story_history[-1]["role"] == "ai":
                st.session_state.story_history.pop()
                extract_characters()
                st.rerun()

    with col_b:
        if st.button("🎨 Visualization Prompt", use_container_width=True):
            if st.session_state.story_history:
                last = st.session_state.story_history[-1]["content"]
                viz = call_llm(f"Create a detailed cinematic image prompt for Flux or Midjourney based on this scene:\n\n{last}")
                if viz:
                    st.text_area("Copy this prompt:", viz, height=120)

    with col_c:
        if st.button("📥 Export Markdown", use_container_width=True):
            story_md = f"# {st.session_state.title}\n\n**Genre:** {st.session_state.genre}\n\n"
            for entry in st.session_state.story_history:
                role = "You" if entry["role"] == "user" else "AI"
                story_md += f"### {role}\n\n{entry['content']}\n\n"
            st.download_button("Download .md", story_md, 
                             f"{st.session_state.title.replace(' ', '_')}.md", "text/markdown")

st.caption("✅ Final Version | Lighter Model + All Features")