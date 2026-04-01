import streamlit as st
import anthropic
import base64
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FridgeChef",
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
.section-broke {
    border-left: 4px solid #e74c3c;
    padding-left: 12px;
    margin-bottom: 8px;
}
.section-alpha {
    border-left: 4px solid #f39c12;
    padding-left: 12px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    # Streamlit Cloud uses st.secrets; local dev uses .env
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        st.error("❌ ANTHROPIC_API_KEY not found. Add it to your .env (local) or Streamlit secrets (cloud).")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def identify_ingredients(image_bytes: bytes, media_type: str) -> list[str]:
    """Send image to Claude and return a list of detected ingredient strings."""
    client = get_client()
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Look at this photo of someone's fridge or groceries. "
                        "List every food item and ingredient you can see. "
                        'Return ONLY a JSON array of strings, for example: '
                        '["chicken breast", "eggs", "butter", "garlic", "onion"]. '
                        "Just the JSON array — no explanation, no markdown."
                    ),
                },
            ],
        }],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped it
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: best-effort parse
        return [item.strip(' "\'') for item in raw.strip("[]").split(",") if item.strip()]


def recipe_stream(ingredients: list[str]):
    """
    Generator that streams the recipe text from Claude.
    Yields string chunks so Streamlit's st.write_stream can consume it.
    """
    client = get_client()
    ingredients_line = ", ".join(ingredients)

    system_msg = (
        "You are a brutally funny but genuinely helpful chef. "
        "Your job is to give real, delicious recipes — but with personality. "
        "Never break character. Always be fun, a little roast-y, and actually useful."
    )

    user_msg = (
        "The user just scanned their fridge. Here is what they have:\n\n"
        f"**{ingredients_line}**\n\n"
        "Generate TWO full recipes. Each recipe should use MOST of what they already have, "
        "but can suggest up to 5 extra ingredients to buy. The food should actually taste great.\n\n"
        "Use this EXACT format — no deviations:\n\n"
        "---\n"
        "## 💸 BROKE BITCH MODE\n\n"
        "### [Recipe Name]\n\n"
        "*[1–2 sentence funny description of the vibe and why broke people make this]*\n\n"
        "**✅ What you already have:**\n"
        "- [ingredient from their list]\n"
        "- [ingredient from their list]\n\n"
        "**🛒 What you need to buy:**\n"
        "- [budget item] — ~$[price]\n"
        "  *(Choose cheap proteins: chicken thigh, tilapia, ground beef, eggs, canned tuna, etc.)*\n\n"
        "**👨‍🍳 How to make it (4–6 steps):**\n"
        "1. [step]\n"
        "2. [step]\n\n"
        "**🔥 The verdict:** [One snarky sentence about why this actually slaps despite costing $8]\n\n"
        "---\n"
        "## 👑 ALPHA CHAD MODE\n\n"
        "### [Recipe Name]\n\n"
        "*[1–2 sentence funny description of the bougie vibe — aspirational, a little absurd]*\n\n"
        "**✅ What you already have:**\n"
        "- [ingredient from their list]\n"
        "- [ingredient from their list]\n\n"
        "**🛒 What you need to buy:**\n"
        "- [REQUIRED: one premium protein — wagyu beef, filet mignon, lobster tail, king crab legs, or prime ribeye] — ~$[price]\n"
        "- [other premium or specialty ingredients] — ~$[price]\n\n"
        "**👨‍🍳 How to make it (4–6 steps, sounds fancy):**\n"
        "1. [step]\n"
        "2. [step]\n\n"
        "**💎 The verdict:** [One sentence about why real ones eat like this]\n\n"
        "---\n"
        "## 🛒 YOUR SHOPPING LIST\n\n"
        "**Broke Bitch run (~$[total range]):**\n"
        "- [ ] [item] — ~$[price]\n\n"
        "**Alpha Chad haul (~$[total range]):**\n"
        "- [ ] [item] — ~$[price]\n\n"
        "---\n\n"
        "Keep the energy fun. Make the food genuinely good. These are real meals real people would cook."
    )

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=2500,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🍳 FridgeChef")
st.markdown("*Snap your fridge. Get two recipes. Know what to buy.*")
st.divider()

uploaded_file = st.file_uploader(
    "📸 Upload a photo of your fridge or groceries",
    type=["jpg", "jpeg", "png", "webp"],
)

if uploaded_file:
    col_img, col_cta = st.columns([1, 1.4])

    with col_img:
        st.image(uploaded_file, caption="Your fridge", use_container_width=True)

    with col_cta:
        st.markdown("### Here's the plan:")
        st.markdown("**🔍 Step 1** — Claude scans your photo and lists every ingredient")
        st.markdown("**💸 Step 2** — You get the *Broke Bitch* recipe (budget, filling, actually good)")
        st.markdown("**👑 Step 3** — You get the *Alpha Chad* upgrade (premium, aspirational, absurd)")
        st.markdown("**🛒 Step 4** — A shopping list for each so you know exactly what to grab")
        st.markdown("")

        go = st.button("🚀 Analyze My Fridge", type="primary", use_container_width=True)

    if go:
        image_bytes = uploaded_file.getvalue()
        media_type = uploaded_file.type  # e.g. "image/jpeg"

        st.divider()

        # ── Step 1: Identify ingredients ─────────────────────────────────────
        with st.spinner("🔍 Scanning your ingredients..."):
            ingredients = identify_ingredients(image_bytes, media_type)

        if not ingredients:
            st.warning("Couldn't make out any ingredients clearly. Try a brighter, closer photo!")
            st.stop()

        st.subheader("🥦 Ingredients I found:")
        tags_html = "".join(
            f'<span class="ingredient-tag">{ing}</span>' for ing in ingredients
        )
        st.markdown(tags_html, unsafe_allow_html=True)
        st.markdown("")

        st.divider()

        # ── Step 2: Stream recipes ────────────────────────────────────────────
        st.subheader("📋 Your Recipes")

        with st.spinner("Cooking up your options..."):
            st.write_stream(recipe_stream(ingredients))

        st.divider()
        st.success("✅ Done! Screenshot your shopping list before you head out.")

        if st.button("📸 Scan Another Fridge"):
            st.rerun()

else:
    # Landing state — explain the app before they upload
    st.markdown("### How it works")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("#### 📸 Snap\nTake a clear photo of your open fridge or lay your groceries on the counter.")
    with c2:
        st.markdown("#### 🔍 Scan\nClaude AI reads the photo and identifies every ingredient it can see.")
    with c3:
        st.markdown("#### 🍽️ Choose\nGet two recipes: one budget meal, one baller upgrade.")
    with c4:
        st.markdown("#### 🛒 Shop\nA checklist tells you exactly what to pick up for each option.")

    st.markdown("")
    st.info("👆 Upload a photo above to get started.")
