import os
import re
from collections import Counter, defaultdict
import sys
import io

# Für UTF-8-Ausgabe auch in PyCharm
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Kritische Wortkategorien
TABUWÖRTER = {
    "persönlich": {"ich", "wir", "mein", "meine", "unser", "unsere", "mich", "mir", "uns"},
    "umgangssprachlich": {"krass", "cool", "mega", "irgendwie", "naja", "halt"},
    "vage": {"man", "einige", "viele", "manche", "öfter", "teilweise", "meistens"}
}

def clean_latex_text(text):
    replacements = {
        r"\"a": "ä", r"\"o": "ö", r"\"u": "ü",
        r"\"A": "Ä", r"\"O": "Ö", r"\"U": "Ü",
        r"\'e": "é", r"\ss{}": "ß", r"\ss": "ß",
        r"~": " ", r"\&": "&", r"\%": "%"
    }
    for latex, char in replacements.items():
        text = text.replace(latex, char)
    text = re.sub(r"\\[a-zA-Z]+\{[^}]*}", "", text)
    text = re.sub(r"%.*", "", text)
    return text

def extract_words_from_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(filename, "r", encoding="latin-1") as f:
            text = f.read()
            text = text.encode("latin-1").decode("utf-8", errors="replace")
    text = clean_latex_text(text)
    return re.findall(r"\b\w+\b", text)

def get_input_files_from_main(main_file="main.tex"):
    if not os.path.exists(main_file):
        print("Fehler: main.tex nicht gefunden.")
        return []
    with open(main_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    files = []
    for line in lines:
        match = re.match(r"\\input{(.+)}", line)
        if match:
            section = match.group(1).strip() + ".tex"
            if os.path.exists(section):
                files.append(section)
            else:
                print(f"Warnung: {section} nicht gefunden.")
    return files

def analyse_tabuwörter(files):
    vorkommen = []
    for file in files:
        words = extract_words_from_file(file)
        counts = Counter(word.lower() for word in words)
        for kategorie, wörter in TABUWÖRTER.items():
            for wort in wörter:
                if wort in counts:
                    vorkommen.append((file, kategorie, wort, counts[wort]))
    return vorkommen

def print_uebersicht(vorkommen):
    print("\nDetailübersicht einzelner Wörter (nach Datei sortiert):")
    print("-" * 60)
    for file, kategorie, wort, anzahl in sorted(vorkommen, key=lambda x: (x[0], -x[3], x[2])):
        print(f"{file:<25} → {wort:<12} ({kategorie:<15}) {anzahl}×")

def main():
    files = get_input_files_from_main("main.tex")
    if not files:
        return
    vorkommen = analyse_tabuwörter(files)
    print_uebersicht(vorkommen)

if __name__ == "__main__":
    main()
