from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)

# Настройка ключа OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route('/', methods=['POST'])
def dialog():
    try:
        req = request.get_json()

        # Извлекаем текст запроса от Алисы
        user_input = req['request']['original_utterance']

        # Запрос к OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты — дерзкий, умный ассистент. Отвечай коротко и резко."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=200,
            temperature=0.8
        )

        reply = response.choices[0].message['content'].strip()

        # Ответ Алисе
        return jsonify({
            "response": {
                "text": reply,
                "end_session": False
            },
            "version": req['version']
        })

    except Exception as e:
        return jsonify({
            "response": {
                "text": f"Ошибка: {str(e)}",
                "end_session": True
            },
            "version": "1.0"
        })

@app.route('/', methods=['GET'])
def health_check():
    return "Alice + ChatGPT skill is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
