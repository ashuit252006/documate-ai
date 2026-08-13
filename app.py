import os

import firebase_admin
from firebase_admin import credentials, firestore

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from google import genai
from werkzeug.utils import secure_filename
from pypdf import PdfReader


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()


# ==========================================
# FIREBASE CONNECTION
# ==========================================

# ==========================================
# FIREBASE CONNECTION
# ==========================================

firebase_credentials = os.getenv("FIREBASE_CREDENTIALS_JSON")

if firebase_credentials:
    cred = credentials.Certificate(
        json.loads(firebase_credentials)
    )
else:
    cred = credentials.Certificate("firebase-key.json")

firebase_admin.initialize_app(cred)

db = firestore.client()

print("Firebase Firestore connected successfully!")


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)

# Stores the currently uploaded PDF text
document_text = ""

# Stores the currently uploaded PDF name
document_name = ""


# ==========================================
# GEMINI CONNECTION
# ==========================================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# ==========================================
# UPLOAD FOLDER
# ==========================================

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template("index.html")


# ==========================================
# CHAT
# ==========================================

@app.route("/chat", methods=["POST"])
def chat():

    global document_text
    global document_name

    # ==========================================
    # GET USER MESSAGE
    # ==========================================

    data = request.get_json()

    if not data:

        return jsonify({
            "reply": "Invalid request."
        }), 400

    user_message = data.get("message", "").strip()

    # ==========================================
    # CHECK MESSAGE
    # ==========================================

    if not user_message:

        return jsonify({
            "reply": "Please enter a message."
        }), 400

    # ==========================================
    # CHECK DOCUMENT
    # ==========================================

    if not document_text:

        return jsonify({
            "reply": "Please upload a PDF document first."
        })


    try:

        # ==========================================
        # GEMINI PROMPT
        # ==========================================

        prompt = f"""
You are DocuMate AI, a document question-answering assistant.

Your job is to answer the user's question using ONLY the information
contained in the uploaded document.

IMPORTANT RULES:

1. Use only the uploaded document as the source.
2. Do not use outside knowledge.
3. Do not invent or make up information.
4. Understand the meaning of the user's question.
5. If the user's wording is slightly different from the wording
   in the document, look for closely related terms or topics.
6. If a closely related topic exists in the document, use that
   information to answer the question.
7. If the document uses a different but related term, mention
   the term used in the document.
8. If the answer is not available anywhere in the document,
   say exactly:

"I couldn't find the answer in the uploaded document."

9. Keep answers clear and easy to understand.
10. Use numbered points when explaining multiple items.
11. Do not provide information that is not supported by the document.

DOCUMENT NAME:
{document_name}

DOCUMENT CONTENT:
{document_text}

USER QUESTION:
{user_message}
"""


        # ==========================================
        # GEMINI API
        # ==========================================

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        bot_reply = response.text


        # ==========================================
        # SAVE CHAT HISTORY TO FIREBASE
        # ==========================================

        db.collection("chat_history").add({

            "question": user_message,

            "answer": bot_reply,

            "document_name": document_name,

            "timestamp": firestore.SERVER_TIMESTAMP

        })

        print("Chat history saved to Firebase!")


        # ==========================================
        # RETURN ANSWER TO FRONTEND
        # ==========================================

        return jsonify({
            "reply": bot_reply
        })


    except Exception as e:

        print("Gemini/Firebase Error:", e)

        return jsonify({
            "reply": "Sorry, something went wrong."
        }), 500


# ==========================================
# PDF UPLOAD
# ==========================================

@app.route("/upload", methods=["POST"])
def upload_document():

    global document_text
    global document_name


    # ==========================================
    # CHECK FILE
    # ==========================================

    if "documentFile" not in request.files:

        return jsonify({
            "success": False,
            "message": "No document was selected."
        }), 400


    file = request.files["documentFile"]


    # ==========================================
    # CHECK FILE NAME
    # ==========================================

    if file.filename == "":

        return jsonify({
            "success": False,
            "message": "No document was selected."
        }), 400


    # ==========================================
    # CHECK PDF
    # ==========================================

    if not file.filename.lower().endswith(".pdf"):

        return jsonify({
            "success": False,
            "message": "Only PDF files are allowed."
        }), 400


    # ==========================================
    # SECURE FILE NAME
    # ==========================================

    filename = secure_filename(file.filename)

    document_name = filename


    # ==========================================
    # CREATE FILE PATH
    # ==========================================

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )


    # ==========================================
    # SAVE PDF
    # ==========================================

    file.save(file_path)

    print(
        f"PDF uploaded successfully: {filename}"
    )


    # ==========================================
    # PDF TEXT EXTRACTION
    # ==========================================

    try:

        reader = PdfReader(file_path)

        extracted_text = ""


        # ==========================================
        # READ EVERY PAGE
        # ==========================================

        for page in reader.pages:

            text = page.extract_text()

            if text:

                extracted_text += text + "\n"


        # ==========================================
        # CHECK EXTRACTED TEXT
        # ==========================================

        if not extracted_text.strip():

            return jsonify({
                "success": False,
                "message": "PDF uploaded, but no readable text was found."
            }), 400


        # ==========================================
        # STORE DOCUMENT TEXT
        # ==========================================

        document_text = extracted_text


        print(
            "PDF text extracted successfully!"
        )

        print(
            "First 1000 characters:"
        )

        print(
            extracted_text[:1000]
        )


    except Exception as e:

        print(
            "PDF Extraction Error:",
            e
        )

        return jsonify({

            "success": False,

            "message":
                "PDF uploaded, but text extraction failed."

        }), 500


    # ==========================================
    # SAVE DOCUMENT INFORMATION TO FIREBASE
    # ==========================================

    try:

        db.collection("documents").add({

            "document_name": filename,

            "text_length": len(document_text),

            "uploaded_at": firestore.SERVER_TIMESTAMP

        })

        print(
            "Document information saved to Firebase!"
        )


    except Exception as e:

        print(
            "Firebase Document Error:",
            e
        )


    # ==========================================
    # RESPONSE
    # ==========================================

    return jsonify({

        "success": True,

        "message":
            f"{filename} uploaded and processed successfully!",

        "filename": filename

    })


# ==========================================
# RUN FLASK
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True
    )