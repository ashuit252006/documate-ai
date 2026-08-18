import os
import json

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

try:

    firebase_credentials = os.getenv(
        "FIREBASE_CREDENTIALS_JSON"
    )

    if firebase_credentials:

        cred = credentials.Certificate(
            json.loads(firebase_credentials)
        )

    else:

        cred = credentials.Certificate(
            "firebase-key.json"
        )

    if not firebase_admin._apps:

        firebase_admin.initialize_app(cred)

    db = firestore.client()

    print(
        "Firebase Firestore connected successfully!"
    )

except Exception as e:

    print(
        "Firebase connection error:",
        e
    )

    db = None


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)


# ==========================================
# DOCUMENT VARIABLES
# ==========================================

document_text = ""

document_name = ""


# ==========================================
# ==========================================
# GEMINI CONNECTION
# ==========================================

from google import genai
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(
    api_key=GEMINI_API_KEY
)

print("Gemini API connected successfully!")

# ==========================================
# UPLOAD FOLDER
# ==========================================

UPLOAD_FOLDER = "uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config[
    "UPLOAD_FOLDER"
] = UPLOAD_FOLDER


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ==========================================
# CHAT
# ==========================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    global document_text
    global document_name


    try:

        # ==========================================
        # GET JSON DATA
        # ==========================================

        data = request.get_json()


        if not data:

            return jsonify({

                "error":
                    "Invalid request.",

                "reply":
                    "Invalid request."

            }), 400


        # ==========================================
        # GET USER QUESTION
        # ==========================================

        user_message = data.get(
            "message",
            ""
        ).strip()


        if not user_message:

            return jsonify({

                "error":
                    "Please enter a question.",

                "reply":
                    "Please enter a question."

            }), 400


        # ==========================================
        # CHECK GEMINI
        # ==========================================

        if not client:

            return jsonify({

                "error":
                    "Gemini API is not configured. Please check GEMINI_API_KEY.",

                "reply":
                    "Gemini API is not configured. Please check GEMINI_API_KEY."

            }), 500


        # ==========================================
        # CHECK DOCUMENT
        # ==========================================

        if not document_text:

            return jsonify({

                "error":
                    "No document uploaded.",

                "reply":
                    "Please upload a PDF document first."

            }), 400


        # ==========================================
        # GEMINI PROMPT
        # ==========================================

        prompt = f"""
You are DocuMate AI, an intelligent document question-answering assistant.

Your task is to answer the user's question using ONLY the uploaded document.

IMPORTANT RULES:

1. Use only information contained in the uploaded document.
2. Do not use outside knowledge.
3. Do not invent or make up information.
4. Understand the meaning of the user's question.
5. If the user's wording is slightly different from the wording in the document,
   search for closely related words, concepts, and topics.
6. If a related topic exists in the document, use that information.
7. If the document uses a different term, mention the term used in the document.
8. If the answer cannot be found in the document, say:

"I couldn't find the answer in the uploaded document."

9. Keep the answer clear and easy to understand.
10. Use numbered points when explaining multiple items.
11. Do not provide unsupported information.
12. Answer directly without unnecessary introduction.

DOCUMENT NAME:
{document_name}

DOCUMENT CONTENT:
{document_text}

USER QUESTION:
{user_message}
"""


        # ==========================================
        # CALL GEMINI
        # ==========================================

        print(
            "Sending question to Gemini..."
        )

        response = client.models.generate_content(

            model="gemini-3.6-flash",

            contents=prompt

        )


        # ==========================================
        # GET GEMINI RESPONSE
        # ==========================================

        bot_reply = response.text


        if not bot_reply:

            bot_reply = (
                "I couldn't generate an answer."
            )


        print(
            "Gemini response received successfully!"
        )


        # ==========================================
        # SAVE CHAT HISTORY TO FIREBASE
        # ==========================================

        if db:

            try:

                db.collection(
                    "chat_history"
                ).add({

                    "question":
                        user_message,

                    "answer":
                        bot_reply,

                    "document_name":
                        document_name,

                    "timestamp":
                        firestore.SERVER_TIMESTAMP

                })

                print(
                    "Chat history saved to Firebase!"
                )

            except Exception as firebase_error:

                print(
                    "Firebase chat history error:",
                    firebase_error
                )


        # ==========================================
        # RETURN ANSWER
        # ==========================================

        return jsonify({

            "success": True,

            "reply": bot_reply

        }), 200


    # ==========================================
    # ERROR HANDLING
    # ==========================================

    except Exception as e:

        print(
            "================================="
        )

        print(
            "CHAT ERROR:"
        )

        print(
            repr(e)
        )

        print(
            "================================="
        )


        return jsonify({

            "success": False,

            "error":
                str(e),

            "reply":
                "Chatbot error: " + str(e)

        }), 500


# ==========================================
# PDF UPLOAD
# ==========================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload_document():

    global document_text
    global document_name


    try:

        # ==========================================
        # CHECK FILE
        # ==========================================

        if "documentFile" not in request.files:

            return jsonify({

                "success": False,

                "error":
                    "No document was selected.",

                "message":
                    "No document was selected."

            }), 400


        file = request.files[
            "documentFile"
        ]


        # ==========================================
        # CHECK FILE NAME
        # ==========================================

        if file.filename == "":

            return jsonify({

                "success": False,

                "error":
                    "No document was selected.",

                "message":
                    "No document was selected."

            }), 400


        # ==========================================
        # CHECK PDF
        # ==========================================

        if not file.filename.lower().endswith(
            ".pdf"
        ):

            return jsonify({

                "success": False,

                "error":
                    "Only PDF files are allowed.",

                "message":
                    "Only PDF files are allowed."

            }), 400


        # ==========================================
        # SECURE FILE NAME
        # ==========================================

        filename = secure_filename(
            file.filename
        )


        document_name = filename


        # ==========================================
        # FILE PATH
        # ==========================================

        file_path = os.path.join(

            app.config[
                "UPLOAD_FOLDER"
            ],

            filename

        )


        # ==========================================
        # SAVE PDF
        # ==========================================

        file.save(
            file_path
        )


        print(
            f"PDF uploaded successfully: {filename}"
        )


        # ==========================================
        # READ PDF
        # ==========================================

    

        reader = PdfReader(
            file_path
        )

        extracted_text = ""

        print(
            f"PDF pages: {len(reader.pages)}"
        )


        # ==========================================
        # EXTRACT EVERY PAGE
        # ==========================================

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                print(
                    f"Extracting page {page_number}..."
                )

                text = page.extract_text()

                if text:

                    extracted_text += (
                        text + "\n"
                    )

            except Exception as page_error:

                print(
                    f"Page {page_number} extraction error:",
                    page_error
                )


        print(
            f"Total extracted text length: {len(extracted_text)}"
        )


    

        # ==========================================
        # CHECK TEXT
        # ==========================================

        if not extracted_text.strip():

            return jsonify({

                "success": False,

                "error":
                    "PDF uploaded, but no readable text was found.",

                "message":
                    "PDF uploaded, but no readable text was found."

            }), 400


        # ==========================================
        # STORE DOCUMENT TEXT
        # ==========================================

        document_text = (
            extracted_text.strip()
        )


        print(
            "PDF text extracted successfully!"
        )

        print(
            "Document:",
            document_name
        )

        print(
            "Text length:",
            len(document_text)
        )

        print(
            "First 1000 characters:"
        )

        print(
            document_text[:1000]
        )


        # ==========================================
        # SAVE DOCUMENT INFO TO FIREBASE
        # ==========================================

        if db:

            try:

                db.collection(
                    "documents"
                ).add({

                    "document_name":
                        filename,

                    "text_length":
                        len(document_text),

                    "uploaded_at":
                        firestore.SERVER_TIMESTAMP

                })

                print(
                    "Document information saved to Firebase!"
                )

            except Exception as firebase_error:

                print(
                    "Firebase document error:",
                    firebase_error
                )


        # ==========================================
        # RETURN SUCCESS
        # ==========================================

        return jsonify({

            "success": True,

            "message":
                f"{filename} uploaded and processed successfully!",

            "filename":
                filename,

            "text_length":
                len(document_text)

        }), 200


    # ==========================================
    # UPLOAD ERROR
    # ==========================================

    except Exception as e:

        print(
            "================================="
        )

        print(
            "UPLOAD ERROR:"
        )

        print(
            repr(e)
        )

        print(
            "================================="
        )


        return jsonify({

            "success": False,

            "error":
                str(e),

            "message":
                "PDF upload failed: " + str(e)

        }), 500


# ==========================================
# RUN FLASK
# ==========================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000

    )