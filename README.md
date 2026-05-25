# SRT Translator — English → Hebrew

A lightweight web app that translates SRT subtitle files from English to Hebrew using the OpenAI GPT API.  
Runs locally on your machine. Your API key is never stored or sent anywhere except to OpenAI.

---

## How it works

Translation is done in three steps:

1. **Parse** — the SRT file is parsed and text is extracted without timecodes
2. **Translate** — GPT translates the full text with complete context (not word-by-word)
3. **Rebuild** — a new SRT file is created with the original timecodes and Hebrew text

RTL rendering is enforced by prepending a Right-to-Left Mark (`U+200F`) to each Hebrew line,  
so punctuation appears correctly on the left side in subtitle players.

---

## Project structure

```
srt_translator/
├── app.py                  # Flask server + translation logic
├── templates/
│   └── index.html          # Drag & drop web interface
├── requirements.txt        # Python dependencies
├── .gitignore
└── README.md
```

---

## Requirements

- Python 3.10 or higher
- An OpenAI API key (get one at https://platform.openai.com/api-keys)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/srt_translator.git
cd srt_translator
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip3 install -r requirements.txt
```

---

## Running the app

```bash
python3 app.py
```

Then open your browser at:

```
http://localhost:5000
```

---

## Usage

1. Enter your OpenAI API key in the field at the top
2. Drag and drop your file(s) into the drop zone, or click to browse
3. Click **Translate**
4. The translated file downloads automatically when done

### Supported input formats

| What you drop | What you get |
|---------------|--------------|
| Single `.srt` file | `filename_hebrew.srt` |
| Multiple `.srt` files | `translated_hebrew.zip` |
| `.zip` containing SRT files | `translated_hebrew.zip` |

---

## Configuration

Default settings are defined at the top of `app.py`:

```python
MODEL       = "gpt-4o"   # OpenAI model to use
TEMPERATURE = 0.1        # Lower = more accurate and consistent
CHUNK_SIZE  = 80         # Subtitle blocks per API call
MAX_RETRIES = 3          # Retry attempts on API error
```

### Recommended models

| Model | Notes |
|-------|-------|
| `gpt-4o` | Default — high quality, fast |
| `gpt-4o-mini` | Cheaper, suitable for simple content |
| `gpt-4-turbo` | Quality alternative |

---

## Setting the API key via environment variable

Instead of typing your key in the browser each time, you can set it as an environment variable.  
The app will use it automatically.

```bash
# Linux / macOS
export OPENAI_API_KEY="sk-proj-..."

# Windows CMD
set OPENAI_API_KEY=sk-proj-...

# Windows PowerShell
$env:OPENAI_API_KEY="sk-proj-..."
```

Note: no space between `=` and the key value.

---

## Notes

- The web server runs **locally only** — it is not exposed to the internet
- Files are processed in memory using temporary directories; nothing is saved to disk permanently
- For very large SRT files, reduce `CHUNK_SIZE` in `app.py` to stay within OpenAI token limits
- Upload limit is set to 100 MB (configurable in `app.py`)

---

## License

MIT
