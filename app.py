import streamlit as st
import anthropic
import base64
import json
import os
import io
import random
import time
import threading
from PIL import Image
import pillow_heif
from dotenv import load_dotenv

# Register HEIC/HEIF support with Pillow
pillow_heif.register_heif_opener()

BROKE_LOADING_MESSAGES = [
    "🪙 Calculating a meal made of table scraps...",
    "💸 Checking if you can even afford this...",
    "🥲 Finding recipes that match your financial situation...",
    "🛒 Searching the clearance aisle of the internet...",
    "📉 Cross-referencing your budget with the poverty line...",
    "🍳 Consulting the dollar store cookbook...",
    "🥫 Dusting off the canned goods section...",
    "💀 Assessing the damage in your fridge...",
    "🤑 Stretching those dollars like Olympic athletes...",
    "🧾 Checking if you qualify for this meal financially...",
]

ALPHA_LOADING_MESSAGES = [
    "👑 Sourcing the finest ingredients for your ascension...",
    "🥩 Contacting the wagyu supplier...",
    "🦞 Waking up the lobster...",
    "💎 Polishing the silver cutlery...",
    "🍷 Selecting a wine pairing worthy of your greatness...",
]

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Recipes and Groceries for Dumbdumbs",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.ingredient-tag {
    display: inline-block;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 5px 14px;
    border-radius: 20px;
    margin: 4px;
    font-size: 0.88em;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("❌ ANTHROPIC_API_KEY not found. Add it to your .env (local) or Streamlit secrets (cloud).")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def convert_to_jpeg(image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
    """Convert any image (including HEIC) to JPEG for Claude."""
    if media_type in ("image/heic", "image/heif") or not media_type.startswith("image/"):
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue(), "image/jpeg"
    return image_bytes, media_type


def identify_ingredients(image_bytes: bytes, media_type: str) -> list[str]:
    client = get_client()
    image_bytes, media_type = convert_to_jpeg(image_bytes, media_type)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                },
                {
                    "type": "text",
                    "text": (
                        "Look at this photo of someone's fridge or groceries. "
                        "List every food item and ingredient you can see. "
                        'Return ONLY a JSON array of strings, e.g.: '
                        '["chicken breast", "eggs", "butter", "garlic"]. '
                        "Just the JSON array — no explanation, no markdown."
                    ),
                },
            ],
        }],
    )
    raw = response.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [item.strip(' "\'') for item in raw.strip("[]").split(",") if item.strip()]


BROKE_CUISINES = [
    "Mexican street food", "Southern comfort food", "Asian stir-fry",
    "Italian peasant food", "American diner", "Indian curry",
    "Middle Eastern", "Caribbean", "Greek", "Japanese home cooking",
    "Korean BBQ-inspired", "Tex-Mex", "French bistro on a budget",
    "Cajun", "Filipino", "Thai street food",
]

BROKE_METHODS = [
    "one pan", "sheet pan", "slow cooker vibes", "15-minute weeknight",
    "fried rice style", "pasta-based", "soup or stew", "sandwich or wrap",
    "grain bowl", "egg-based", "taco situation",
]

ALPHA_PROTEINS = [
    "A5 wagyu beef", "filet mignon", "whole lobster tail",
    "king crab legs", "prime dry-aged ribeye", "Chilean sea bass",
    "bluefin tuna sashimi-grade steak", "Alaskan king salmon",
    "foie gras", "rack of lamb",
]

ALPHA_STYLES = [
    "French fine dining", "Japanese omakase-inspired", "steakhouse",
    "coastal Italian", "modern American brasserie", "Spanish tapas elevated",
    "Michelin-star bistro", "NYC rooftop dinner party",
]


def recipe_stream(ingredients: list[str], mode: str):
    """Stream a single recipe (broke or alpha) based on mode."""
    client = get_client()
    ingredients_str = ", ".join(ingredients)

    system_msg = (
        "You are a brutally funny but genuinely helpful chef. "
        "Give real, delicious recipes with personality. "
        "Never break character. Always be fun, a little roast-y, and actually useful. "
        "Every recipe you generate should be genuinely different — different dish, "
        "different cuisine, different cooking method. Never repeat yourself."
    )

    if mode == "broke":
        cuisine = random.choice(BROKE_CUISINES)
        method = random.choice(BROKE_METHODS)
        user_msg = (
            f"The user has these ingredients: {ingredients_str}\n\n"
            f"Generate ONE budget recipe inspired by **{cuisine}** cuisine, "
            f"using a **{method}** approach. Use most of what they have, "
            "suggest up to 5 cheap additions (chicken thigh, tilapia, ground beef, eggs, canned beans, etc.). "
            "Make it feel like a completely different meal — not a generic stir-fry or scramble.\n\n"
            "Use this EXACT format:\n\n"
            "## 💸 BROKE BITCH BOY BUDGET\n\n"
            "### [Recipe Name]\n\n"
            "*[1–2 sentence funny description — why broke people make this and why it actually hits]*\n\n"
            "**✅ What you already have:**\n"
            "- [ingredient from their list]\n\n"
            "**🛒 What you need to buy:**\n"
            "- [budget item] — ~$[price]\n\n"
            "**👨‍🍳 How to make it:**\n"
            "1. [step]\n"
            "2. [step]\n"
            "(4–6 steps total)\n\n"
            "**🔥 The verdict:** [One snarky sentence about why this slaps despite costing $8]\n\n"
            "---\n"
            "## 🛒 YOUR SHOPPING LIST (~$[total estimate])\n"
            "- [ ] [item] — ~$[price]\n\n"
            "Keep it fun and make the food genuinely good."
        )
    else:
        protein = random.choice(ALPHA_PROTEINS)
        style = random.choice(ALPHA_STYLES)
        user_msg = (
            f"The user has these ingredients: {ingredients_str}\n\n"
            f"Generate ONE premium recipe in the style of **{style}**, "
            f"built around **{protein}** as the hero ingredient. "
            "Use most of what they have. Make it feel genuinely impressive and distinct — "
            "not a basic seared steak. Think plating, technique, drama.\n\n"
            "Use this EXACT format:\n\n"
            "## 👑 ALPHA CHAD FEAST\n\n"
            "### [Recipe Name]\n\n"
            "*[1–2 sentence funny bougie description — aspirational, a little absurd, makes them feel like a god]*\n\n"
            "**✅ What you already have:**\n"
            "- [ingredient from their list]\n\n"
            "**🛒 What you need to buy:**\n"
            f"- {protein} — ~$[price]\n"
            "- [other premium additions] — ~$[price]\n\n"
            "**👨‍🍳 How to make it:**\n"
            "1. [step]\n"
            "2. [step]\n"
            "(4–6 steps, sounds fancy)\n\n"
            "**💎 The verdict:** [One sentence about why alphas eat like this]\n\n"
            "---\n"
            "## 🛒 YOUR SHOPPING LIST (~$[total estimate])\n"
            "- [ ] [item] — ~$[price]\n\n"
            "Keep it fun and make the food genuinely impressive."
        )

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🍳 Recipes and Groceries for Dumbdumbs")
st.markdown("*Snap your food. Choose your tier. Buy crap. Get cooking.*")
st.divider()

uploaded_file = st.file_uploader(
    "📸 Upload a photo of your fridge or groceries",
    type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
)

if uploaded_file:
    col_img, col_cta = st.columns([1, 1.4])

    with col_img:
        st.image(uploaded_file, caption="Your fridge", use_container_width=True)

    with col_cta:
        st.markdown("### Here's the plan:")
        st.markdown("**🔍 Step 1** — We figure out what you got to work with.")
        st.markdown("**💸 Step 2** — You decide how much of a baller you are.")
        st.markdown("**🛒 Step 3** — Get your shopping list.")
        st.markdown("**🍽️ Step 4** — FEAST!")
        st.markdown("")
        go = st.button("🚀 Analyze My Fridge", type="primary", use_container_width=True)

    # Reset state when Analyze is clicked
    if go:
        st.session_state.ingredients = None
        st.session_state.recipe_mode = None
        st.session_state.recipe_text = None
        st.session_state.image_bytes = uploaded_file.getvalue()
        st.session_state.media_type = uploaded_file.type

    # Show results if we have an analysis in progress or complete
    if go or st.session_state.get("ingredients") is not None:
        st.divider()

        # ── Step 1: Identify ingredients (once, then cache) ──────────────────
        if not st.session_state.get("ingredients"):
            with st.spinner("🔍 Scanning your ingredients..."):
                ingredients = identify_ingredients(
                    st.session_state.image_bytes,
                    st.session_state.media_type,
                )
            if not ingredients:
                st.warning("Couldn't make out any ingredients. Try a brighter, closer photo!")
                st.stop()
            st.session_state.ingredients = ingredients

        ingredients = st.session_state.ingredients

        st.subheader("🥦 Ingredients I found:")
        tags_html = "".join(f'<span class="ingredient-tag">{ing}</span>' for ing in ingredients)
        st.markdown(tags_html, unsafe_allow_html=True)
        st.markdown("")
        st.divider()

        # ── Step 2: Tier selection ────────────────────────────────────────────
        if not st.session_state.get("recipe_mode"):
            st.subheader("Choose your recipe tier:")
            col_b, col_a = st.columns(2)
            with col_b:
                if st.button("💸 Broke Bitch Boy Budget", use_container_width=True, type="primary"):
                    st.session_state.recipe_mode = "broke"
                    st.session_state.recipe_text = None
                    st.rerun()
            with col_a:
                if st.button("👑 Alpha Chad Feast", use_container_width=True, type="primary"):
                    st.session_state.recipe_mode = "alpha"
                    st.session_state.recipe_text = None
                    st.rerun()

        # ── Step 3: Show recipe ───────────────────────────────────────────────
        else:
            mode = st.session_state.recipe_mode
            label = "💸 Broke Bitch Boy Budget" if mode == "broke" else "👑 Alpha Chad Feast"
            st.subheader(f"Your recipe: {label}")

            # Stream if not yet generated, otherwise show cached text
            if not st.session_state.get("recipe_text"):
                pool = BROKE_LOADING_MESSAGES if mode == "broke" else ALPHA_LOADING_MESSAGES
                # Shuffle so order feels fresh each time
                phrases = pool.copy()
                random.shuffle(phrases)

                # Generate recipe in a background thread
                result = {"text": None}
                def generate():
                    result["text"] = "".join(recipe_stream(ingredients, mode))
                t = threading.Thread(target=generate)
                t.start()

                # Rotate phrases every 3 seconds while recipe generates
                placeholder = st.empty()
                idx = 0
                min_duration = 5  # always show at least this long
                start = time.time()
                while t.is_alive() or (time.time() - start) < min_duration:
                    phrase = phrases[idx % len(phrases)]
                    placeholder.markdown(f"### {phrase}")
                    idx += 1
                    time.sleep(3)
                t.join()
                placeholder.empty()

                # Display full recipe all at once
                full_text = result["text"]
                st.session_state.recipe_text = full_text

            # ── Try Another button (above recipe) ────────────────────────────
            if st.button("🎲 Try Another Option", use_container_width=True, key="try_another_top"):
                st.session_state.recipe_text = None
                st.rerun()

            st.markdown(st.session_state.recipe_text)

            # ── Export section ────────────────────────────────────────────────
            st.divider()
            st.markdown("### 📤 Save this recipe")

            recipe_text = st.session_state.recipe_text
            label = "Broke Bitch Boy Budget" if mode == "broke" else "Alpha Chad Feast"
            export_text = f"Recipes and Groceries for Dumbdumbs\n{label}\n\n{recipe_text}"
            filename = "broke-bitch-recipe.txt" if mode == "broke" else "alpha-chad-recipe.txt"

            col_e1, col_e2 = st.columns(2)

            with col_e1:
                # Download as .txt — works on all devices
                st.download_button(
                    label="📥 Download Recipe + List",
                    data=export_text,
                    file_name=filename,
                    mime="text/plain",
                    use_container_width=True,
                )

            with col_e2:
                # Copy to clipboard via JavaScript
                escaped = export_text.replace("`", "'").replace("\\", "\\\\").replace("\n", "\\n")
                st.components.v1.html(f"""
                    <button onclick="
                        navigator.clipboard.writeText(`{escaped}`).then(function() {{
                            document.getElementById('copy-btn').innerText = '✅ Copied!';
                            setTimeout(function() {{
                                document.getElementById('copy-btn').innerText = '📋 Copy to Clipboard';
                            }}, 2000);
                        }});
                    "
                    id="copy-btn"
                    style="
                        width: 100%;
                        padding: 10px;
                        background-color: #ff4b4b;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        font-size: 15px;
                        font-weight: 600;
                        cursor: pointer;
                    ">
                        📋 Copy to Clipboard
                    </button>
                """, height=50)

            st.caption("💡 iPhone users: tap Copy, open Notes, paste. Done.")

            # ── Bottom nav buttons ────────────────────────────────────────────
            st.divider()
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                if st.button("🎲 Try Another Option", use_container_width=True, key="try_another_bottom"):
                    st.session_state.recipe_text = None
                    st.rerun()
            with col_r2:
                if st.button("🔄 Switch Tiers", use_container_width=True):
                    st.session_state.recipe_mode = None
                    st.session_state.recipe_text = None
                    st.rerun()
            with col_r3:
                if st.button("📸 Scan Another Fridge", use_container_width=True):
                    for key in ["ingredients", "recipe_mode", "recipe_text", "image_bytes", "media_type"]:
                        st.session_state.pop(key, None)
                    st.rerun()

else:
    st.markdown("### How it works")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("📸 **Snap**\n\nTake a clear photo of your open fridge or lay your groceries on the counter.")
    with c2:
        st.markdown("🔍 **Scan**\n\nClaude AI reads the photo and identifies every ingredient it can see.")
    with c3:
        st.markdown("🍽️ **Choose**\n\nPick your tier: Broke Bitch budget or Alpha Chad feast.")
    with c4:
        st.markdown("🛒 **Shop**\n\nGet a checklist of exactly what to pick up for your chosen meal.")

    st.markdown("")
    st.info("👆 Upload a photo above to get started.")
