from flask import Flask, request, jsonify
import openai

app = Flask(__name__)
openai.api_key = OPENAI_API_KEY

@app.route("/", methods=["POST"])
def index():
    data = request.json
    user_text = data['request']['original_utterance']

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": open("prompt.txt", "r", encoding="utf-8").read()},
            {"role": "user", "content": user_text}
        ]
    )

    reply = response.choices[0].message["content"].strip()

    return jsonify({
        "response": {
            "text": reply,
            "end_session": False
        },
        "version": data["version"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
