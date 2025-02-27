import librosa
import numpy as np
from music21 import note, stream
from fpdf import FPDF
from pydub import AudioSegment
import os
from flask import Flask, request, send_file, render_template_string
import tempfile

app = Flask(__name__)

def load_audio(file_path):
    audio = AudioSegment.from_file(file_path)
    audio = audio.set_channels(1)
    temp_wav = "temp.wav"
    audio.export(temp_wav, format="wav")
    y, sr = librosa.load(temp_wav, mono=True)
    os.remove(temp_wav)
    return y, sr

def detect_tuning(y, sr):
    return ["E", "A", "D", "G", "B", "E"]

def analyze_notes(y, sr, chunk_length=5.0):  # Smaller 5-second chunks
    chunk_samples = int(chunk_length * sr)
    notes = []
    for start in range(0, len(y), chunk_samples):
        end = min(start + chunk_samples, len(y))
        y_chunk = y[start:end]
        chroma = librosa.feature.chroma_stft(y=y_chunk, sr=sr, hop_length=2048)  # Bigger hop_length
        onsets = librosa.onset.onset_detect(y=y_chunk, sr=sr, hop_length=2048)
        for onset in onsets:
            absolute_onset = (start // 2048) + onset
            pitch = np.argmax(chroma[:, onset])
            notes.append((absolute_onset, pitch))
    return notes

def map_pitch_to_fret(pitch, tuning):
    string_idx = pitch % 6
    fret = pitch // 6
    string = tuning[string_idx]
    return fret, string

def notes_to_tab(notes, tuning):
    tab = {s: ["-" for _ in range(200)] for s in tuning}
    for i, (onset, pitch) in enumerate(notes):
        fret, string = map_pitch_to_fret(pitch, tuning)
        if i < 200:
            tab[string][i] = str(fret) if fret < 10 else str(fret)[-1]
    tab_str = "\n".join(f"{s}|{'-'.join(tab[s])}|" for s in tuning[::-1])
    return tab_str

def export_tab(tab, filename):
    with open(f"{filename}.txt", "w") as f:
        f.write(tab)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=12)
    for line in tab.split("\n"):
        pdf.cell(200, 10, txt=line, ln=True)
    pdf.output(f"{filename}.pdf")

def transcribe_to_tab(file_path, output_name):
    y, sr = load_audio(file_path)
    tuning = detect_tuning(y, sr)
    notes = analyze_notes(y, sr, chunk_length=5.0)
    tab = notes_to_tab(notes, tuning)
    export_tab(tab, output_name)
    os.remove(file_path)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files:
            return "No file uploaded", 400
        file = request.files["file"]
        if file.filename == "":
            return "No file selected", 400
        if file and file.filename.lower().endswith((".mp3", ".wav")):
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
                input_file = temp_file.name
                file.save(input_file)
            output_name = os.path.splitext(file.filename)[0]
            try:
                transcribe_to_tab(input_file, output_name)
                txt_path = f"{output_name}.txt"
                pdf_path = f"{output_name}.pdf"
                return f"""
                <p>Processing complete! Download your files:</p>
                <a href="/download/{output_name}.txt">Download {output_name}.txt</a><br>
                <a href="/download/{output_name}.pdf">Download {output_name}.pdf</a>
                """
            except Exception as e:
                return f"Error processing file: {str(e)}", 500
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Guitar Tab Transcriber</title></head>
    <body>
        <h1>Upload an MP3 or WAV File</h1>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".mp3,.wav">
            <input type="submit" value="Transcribe">
        </form>
    </body>
    </html>
    """)

@app.route("/download/<filename>")
def download(filename):
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
