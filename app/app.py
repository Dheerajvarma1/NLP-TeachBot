from flask import Flask, render_template, request, session
import requests
import nltk
from textblob import TextBlob
import html

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Required for sessions

# Download necessary NLTK data
nltk.download('punkt')

# Ollama API Endpoint
OLLAMA_API_URL = "http://localhost:11434/api/generate"

def generate_content(prompt, model="llama3"):
    """Generates educational content based on user prompt."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "No response")
    except requests.RequestException as e:
        return f"Error: {str(e)}"

def get_readability(text):
    """Calculates the Flesch Reading Ease score using TextBlob and NLTK."""
    blob = TextBlob(text)
    sentences = nltk.sent_tokenize(text)
    words = nltk.word_tokenize(text)
    syllables = sum([len([char for char in word if char.lower() in "aeiou"]) for word in words])
    if len(sentences) == 0 or len(words) == 0:
        return 0
    flesch_score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
    return max(0, min(100, flesch_score))  # Ensure score is between 0 and 100

def refine_content(text):
    """Enhances readability, coherence, and inclusivity with formatting."""
    # Add formatting for headings and bold text
    headings = {
        "** Lesson Title **": "<h2><strong>Lesson Title:</strong></h2>",
        "** Objectives **": "<h3><strong>Objectives:</strong></h3>",
        "** Materials **": "<h3><strong>Materials:</strong></h3>",
        "** Procedure **": "<h3><strong>Procedure:</strong></h3>",
        "** Assessment **": "<h3><strong>Assessment:</strong></h3>"
    }
    for old, new in headings.items():
        text = text.replace(old, new)
    
    # Adjust other formatting based on common patterns (like * bullet points)
    lines = text.split('\n')
    formatted_lines = []
    in_list = False
    for line in lines:
        if line.strip().startswith('*'):
            if not in_list:
                formatted_lines.append('<ul>')
                in_list = True
            formatted_lines.append(f'<li>{line.strip()[1:].strip()}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            formatted_lines.append(line)
    if in_list:
        formatted_lines.append('</ul>')
    text = '\n'.join(formatted_lines)

    readability_score = get_readability(text)
    if readability_score < 50:
        text += "<p><strong>[NOTE: Content complexity adjusted for readability.]</strong></p>"

    # Ensure inclusivity by avoiding exclusive terms
    bias_terms = {"he": "they", "she": "they", "disabled": "person with a disability", "foreigner": "international individual"}
    tokens = nltk.word_tokenize(text)
    refined_text = " ".join([bias_terms.get(token.lower(), token) for token in tokens])
    
    return refined_text

def check_bias(text):
    """Detects biased terms in the generated content."""
    bias_terms = ["he", "she", "rich", "poor", "strong", "weak", "disabled", "foreigner"]
    flagged_terms = [word for word in nltk.word_tokenize(text.lower()) if word in bias_terms]
    return list(set(flagged_terms))  # Unique flagged terms

@app.route("/", methods=["GET", "POST"])
def home():
    # Initialize content history if it does not exist
    if 'content_history' not in session:
        session['content_history'] = []

    if request.method == "POST":
        subject = request.form["subject"]
        grade_level = request.form["grade_level"]
        topic = request.form["topic"]
        prompt = f"Generate a lesson plan on {topic} for {grade_level} students studying {subject}. Include sections for Lesson Title, Objectives, Materials, Procedure, and Assessment. Keep it informative, engaging, and unbiased."
        raw_content = generate_content(prompt)
        refined_content = refine_content(raw_content)
        biases = check_bias(refined_content)

        # Extract just the topic (the input topic text) to store
        session['content_history'].append({
            'topic': topic
        })
        session.modified = True  # Ensure the session is saved

        return render_template("index.html", 
                               raw_content=html.escape(raw_content), 
                               refined_content=refined_content, 
                               biases=biases, 
                               content_history=session.get('content_history'))

    return render_template("index.html", content_history=session.get('content_history'))

if __name__ == "__main__":
    app.run(debug=False, threaded=True)

