"""
Kaloriya Hisoblagich - Rasm orqali ovqat kaloriyasini aniqlovchi ilova
Ishga tushirish: streamlit run app.py
"""

import streamlit as st
import base64
import json
import os
import re
import requests
from datetime import date

# ============================================================
# SOZLAMALAR
# ============================================================
DATA_FILE = "kaloriya_data.json"
API_KEY_ENV = "OPENROUTER_API_KEY"  # API kalitni shu muhit o'zgaruvchisiga qo'ying
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"  # xohlasangiz "openai/gpt-4o" ga almashtiring

st.set_page_config(page_title="Kaloriya Hisoblagich", page_icon="🍽", layout="centered")


# ============================================================
# MA'LUMOTLARNI SAQLASH / O'QISH (JSON fayl orqali)
# ============================================================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"profile": None, "logs": {}}  # logs: {"YYYY-MM-DD": [ {taom...}, ... ]}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if "data" not in st.session_state:
    st.session_state.data = load_data()

if "pending_result" not in st.session_state:
    st.session_state.pending_result = None  # oxirgi tahlil natijasi (Qo'shish/O'chirish kutilmoqda)


# ============================================================
# TDEE HISOBLASH (Mifflin-St Jeor formulasi)
# ============================================================
ACTIVITY_LEVELS = {
    "Kam harakat": 1.2,
    "O'rtacha faol": 1.55,
    "Juda faol": 1.9,
}


def calc_tdee(jins, yosh, boy, vazn, faollik_koef):
    if jins == "Erkak":
        bmr = 10 * vazn + 6.25 * boy - 5 * yosh + 5
    else:
        bmr = 10 * vazn + 6.25 * boy - 5 * yosh - 161
    return round(bmr * faollik_koef)


# ============================================================
# OPENROUTER VISION ORQALI RASMNI TAHLIL QILISH
# ============================================================
def analyze_food_image(image_bytes, media_type="image/jpeg"):
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        return {"error": "OPENROUTER_API_KEY muhit o'zgaruvchisi topilmadi. API kalitni sozlang."}

    b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{b64_image}"

    prompt = (
        "Bu rasmdagi taomni aniqla va FAQAT quyidagi JSON formatida javob qaytar, "
        "boshqa hech qanday matn, izoh yoki markdown belgisi qo'shma:\n"
        '{"taom_nomi": "...", "porsiya_grammda": 000, "kaloriya": 000, '
        '"oqsil_g": 00, "yog_g": 00, "uglevod_g": 00}\n'
        "Eng ehtimoliy taxminni ber, aniqlik uchun savol berma."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "max_tokens": 500,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"].strip()
        # Ba'zan model ```json``` bilan o'rab yuborishi mumkin - tozalaymiz
        raw_text = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip())
        result = json.loads(raw_text)
        return result
    except json.JSONDecodeError:
        return {"error": "Rasmni aniqlab bo'lmadi (JSON xato). Qaytadan urinib ko'ring."}
    except requests.exceptions.RequestException as e:
        return {"error": f"API so'rovida xatolik: {e}"}
    except Exception as e:
        return {"error": f"Xatolik yuz berdi: {e}"}


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================
def today_key():
    return str(date.today())


def get_today_log():
    return st.session_state.data["logs"].get(today_key(), [])


def add_to_log(item):
    key = today_key()
    st.session_state.data["logs"].setdefault(key, []).append(item)
    save_data(st.session_state.data)


def remove_from_log(index):
    key = today_key()
    if key in st.session_state.data["logs"] and 0 <= index < len(st.session_state.data["logs"][key]):
        st.session_state.data["logs"][key].pop(index)
        save_data(st.session_state.data)


def total_today_kcal():
    return sum(item["kaloriya"] for item in get_today_log())


# ============================================================
# 1) PROFIL FORMASI (agar profil hali kiritilmagan bo'lsa)
# ============================================================
st.title("🍽 Kaloriya Hisoblagich")

if st.session_state.data["profile"] is None:
    st.subheader("Avval profilingizni to'ldiring")
    with st.form("profil_forma"):
        jins = st.radio("Jinsi", ["Erkak", "Ayol"])
        yosh = st.number_input("Yoshi", min_value=10, max_value=100, value=25)
        boy = st.number_input("Bo'yi (sm)", min_value=100, max_value=250, value=170)
        vazn = st.number_input("Vazni (kg)", min_value=30, max_value=250, value=70)
        faollik = st.selectbox("Faollik darajasi", list(ACTIVITY_LEVELS.keys()))
        submitted = st.form_submit_button("Saqlash")

        if submitted:
            tdee = calc_tdee(jins, yosh, boy, vazn, ACTIVITY_LEVELS[faollik])
            st.session_state.data["profile"] = {
                "jins": jins,
                "yosh": yosh,
                "boy": boy,
                "vazn": vazn,
                "faollik": faollik,
                "tdee": tdee,
            }
            save_data(st.session_state.data)
            st.rerun()

else:
    profile = st.session_state.data["profile"]

    # Profilni tahrirlash imkoniyati
    with st.expander("⚙️ Profilni tahrirlash"):
        with st.form("profil_tahrir"):
            jins = st.radio("Jinsi", ["Erkak", "Ayol"], index=0 if profile["jins"] == "Erkak" else 1)
            yosh = st.number_input("Yoshi", min_value=10, max_value=100, value=profile["yosh"])
            boy = st.number_input("Bo'yi (sm)", min_value=100, max_value=250, value=profile["boy"])
            vazn = st.number_input("Vazni (kg)", min_value=30, max_value=250, value=profile["vazn"])
            faollik = st.selectbox(
                "Faollik darajasi",
                list(ACTIVITY_LEVELS.keys()),
                index=list(ACTIVITY_LEVELS.keys()).index(profile["faollik"]),
            )
            yangilash = st.form_submit_button("Yangilash")
            if yangilash:
                tdee = calc_tdee(jins, yosh, boy, vazn, ACTIVITY_LEVELS[faollik])
                st.session_state.data["profile"] = {
                    "jins": jins, "yosh": yosh, "boy": boy, "vazn": vazn,
                    "faollik": faollik, "tdee": tdee,
                }
                save_data(st.session_state.data)
                st.rerun()

    tdee = profile["tdee"]
    eaten = total_today_kcal()
    remaining = tdee - eaten

    # ============================================================
    # 2) KUNLIK HISOB PANELI
    # ============================================================
    st.subheader("📊 Bugungi holat")
    col1, col2, col3 = st.columns(3)
    col1.metric("Kunlik me'yor", f"{tdee} kkal")
    col2.metric("Yegan", f"{eaten} kkal")
    col3.metric("Qolgan", f"{remaining} kkal", delta=None)

    progress = min(eaten / tdee, 1.0) if tdee > 0 else 0
    st.progress(progress)
    if remaining < 0:
        st.error(f"⚠️ Kunlik me'yordan {abs(remaining)} kkal oshib ketdingiz!")

    st.divider()

    # ============================================================
    # 3) RASM YUKLASH VA TAHLIL
    # ============================================================
    st.subheader("📸 Ovqat rasmini yuklang")
    uploaded_file = st.file_uploader("Rasm tanlang", type=["jpg", "jpeg", "png", "webp"])

    if uploaded_file is not None and st.session_state.pending_result is None:
        if st.button("🔍 Tahlil qilish"):
            with st.spinner("Rasm tahlil qilinmoqda..."):
                image_bytes = uploaded_file.read()
                ext = uploaded_file.name.split(".")[-1].lower()
                media_type = "image/png" if ext == "png" else "image/webp" if ext == "webp" else "image/jpeg"
                result = analyze_food_image(image_bytes, media_type)
                st.session_state.pending_result = result

    # Natijani ko'rsatish + Qo'shish/O'chirish
    if st.session_state.pending_result is not None:
        result = st.session_state.pending_result
        if "error" in result:
            st.error(result["error"])
            if st.button("Yopish"):
                st.session_state.pending_result = None
                st.rerun()
        else:
            st.success("Tahlil natijasi:")
            taom_nomi = result.get("taom_nomi", "Noma'lum")
            porsiya = result.get("porsiya_grammda", "?")
            kaloriya = result.get("kaloriya", "?")
            oqsil = result.get("oqsil_g", "?")
            yog = result.get("yog_g", "?")
            uglevod = result.get("uglevod_g", "?")
            st.markdown(f"""
            **🍽 Taom:** {taom_nomi}
            **📏 Porsiya:** {porsiya} g
            **🔥 Kaloriya:** {kaloriya} kkal
            **Oqsil:** {oqsil} g | **Yog':** {yog} g | **Uglevod:** {uglevod} g
            """)

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Qo'shish", use_container_width=True):
                    add_to_log(result)
                    st.session_state.pending_result = None
                    st.rerun()
            with col_b:
                if st.button("❌ O'tkazib yuborish", use_container_width=True):
                    st.session_state.pending_result = None
                    st.rerun()

    st.divider()

    # ============================================================
    # 4) BUGUNGI RO'YXAT
    # ============================================================
    st.subheader("📋 Bugun yegan taomlar")
    today_log = get_today_log()
    if not today_log:
        st.info("Hali hech narsa qo'shilmagan.")
    else:
        for i, item in enumerate(today_log):
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{item.get('taom_nomi')}** — {item.get('kaloriya')} kkal ({item.get('porsiya_grammda')} g)")
            if c2.button("🗑", key=f"del_{i}"):
                remove_from_log(i)
                st.rerun()
