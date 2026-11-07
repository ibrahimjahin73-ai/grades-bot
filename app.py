
import os
import json
from flask import Flask, request, jsonify
import re

app = Flask(__name__)

# تحميل الدرجات
with open('grades.json', 'r', encoding='utf-8') as f:
    GRADES = json.load(f)

def normalize_arabic(text):
    """تطبيع النص العربي للبحث"""
    if not text:
        return ""
    text = text.strip().lower()
    # إزالة التشكيل
    text = re.sub(r'[ًٌٍَُِّْ]', '', text)
    # توحيد الهمزات والتاء المربوطة
    text = text.replace('أ','ا').replace('إ','ا').replace('آ','ا')
    text = text.replace('ة','ه').replace('ى','ي')
    text = re.sub(r'\s+', ' ', text)
    return text

def find_student(query):
    """البحث عن الطالب بالاسم"""
    q_norm = normalize_arabic(query)
    if len(q_norm) < 3:
        return []
    
    results = []
    for student in GRADES:
        name_norm = normalize_arabic(student['name'])
        # بحث دقيق أو جزئي
        if q_norm in name_norm or name_norm in q_norm:
            results.append(student)
        else:
            # بحث بالكلمات - على الأقل كلمتين متطابقتين
            q_words = set(q_norm.split())
            name_words = set(name_norm.split())
            common = q_words & name_words
            if len(common) >= 2:
                results.append(student)
    
    return results[:3]  # أقصى 3 نتائج

def get_grade_text(student):
    grade = student['grade']
    try:
        g = float(grade)
        if g >= 18:
            taqdeer = "ممتاز 🌟"
        elif g >= 15:
            taqdeer = "جيد جداً 👍"
        elif g >= 12:
            taqdeer = "جيد ✅"
        elif g >= 10:
            taqdeer = "مقبول ⚠️"
        else:
            taqdeer = "يحتاج متابعة 📚"
    except:
        taqdeer = ""
    
    return f"""مرحبا {student['name']} 👋

📊 *نتيجة اختبار لغتي - ثالث متوسط*
*منتصف الفصل الدراسي الأول 1448*

┌──────────────
│ الاسم: {student['name']}
│ الفصل: {student['class']}
│ الدرجة: *{grade} من 20*
│ التقدير: {taqdeer}
└──────────────

💡 ملاحظة: تم تصحيح سؤال الجوهرة - الإجابة الصحيحة (ملك هيثم)

بالتوفيق! 🌹
- أ. لغتي الخالدة"""

@app.route('/', methods=['GET'])
def home():
    return """
    <h2>بوت درجات لغتي - يعمل ✅</h2>
    <p>عدد الطلاب: """ + str(len(GRADES)) + """</p>
    <p>جرب: /test?name=ابراهيم</p>
    """

@app.route('/test', methods=['GET'])
def test_search():
    name = request.args.get('name','')
    results = find_student(name)
    if not results:
        return jsonify({"found": False, "message": "لم أجد الطالب"})
    return jsonify({"found": True, "results": results, "reply": get_grade_text(results[0])})

# ====== واتساب Cloud API ======
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'my_verify_token_123')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '')

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """تأكيد الويب هوك من ميتا"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Verification failed', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال رسائل واتساب"""
    data = request.get_json()
    try:
        # استخراج الرسالة
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        if 'messages' not in value:
            return 'ok', 200
        
        message = value['messages'][0]
        from_number = message['from']
        text = message['text']['body'] if message['type'] == 'text' else ''
        
        print(f"رسالة من {from_number}: {text}")
        
        # البحث عن الدرجة
        if text.strip() in ['السلام عليكم','سلام','مرحبا','هلا','درجتي','درجة','مساعدة','help']:
            reply = """مرحبا بك في بوت درجات لغتي 👋

أرسل *اسمك الثلاثي* وسأرسل لك درجتك فورا.

مثال: ابراهيم الدوسري
أو: تركي المسبحي

🔒 خصوصية: لا يتم حفظ رقمك"""
        else:
            results = find_student(text)
            if not results:
                reply = f"""عذرا لم أجد اسم "{text}" 🤔

تأكد من:
• كتابة الاسم الثلاثي بشكل صحيح
• مثال: ابراهيم خالد الدوسري

حاول مرة أخرى 👇"""
            elif len(results) > 1:
                names = "\n".join([f"• {r['name']}" for r in results])
                reply = f"""وجدت أكثر من طالب بهذا الاسم:

{names}

أرسل الاسم كاملا مع الفصل 🔍"""
            else:
                reply = get_grade_text(results[0])
        
        # إرسال الرد عبر واتساب
        send_whatsapp_message(from_number, reply)
        
    except Exception as e:
        print(f"خطأ: {e}")
        import traceback
        traceback.print_exc()
    
    return 'ok', 200

def send_whatsapp_message(to, text):
    """إرسال رسالة واتساب"""
    import requests
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print(f"[محاكاة] إرسال إلى {to}: {text}")
        return
    
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    try:
        resp = requests.post(url, headers=headers, json=payload)
        print(f"WhatsApp API response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"فشل الإرسال: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
