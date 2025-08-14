# check_de_caps.py
# Prüft Groß-/Kleinschreibung deutscher Wörter in .tex-Dateien.
# Anpassungen:
# 1) Satzanfang NUR prüfen, wenn vorherige bereinigte Zeile mit .?! endet.
# 2) Englische Wörter (z.B. "classification", "Learning") werden rausgefiltert.
# 3) Inhalte innerhalb \enquote{ ... } vollständig ignorieren.  Früher \("\)

import os
import re
import sys
from collections import defaultdict

try:
    import spacy
    from wordfreq import zipf_frequency
except ImportError:
    print("Bitte installiere Abhängigkeiten:\n  python -m pip install -U spacy wordfreq\n  python -m spacy download de_core_news_sm")
    sys.exit(1)

# spaCy laden
try:
    nlp = spacy.load("de_core_news_sm")
except OSError:
    print("spaCy-Modell 'de_core_news_sm' fehlt.\nInstalliere mit:\n  python -m spacy download de_core_news_sm")
    sys.exit(1)

EXCLUDE_FILES = {"main.tex", "titlepage.tex"}
TEX_EXT = ".tex"

IGNORE_WORDS = {
    "amt","cnn","rnn","lstm","gru","mlp","mt3","yourmt3","omnizart","mfcc","cqt",
    "json","csv","midi","xml","yaml","wav","fps","ui","vr","ros","ros2","rssi","dbm","gpu","cpu"
}
FORMAL_PRONOUNS = {"Sie","Ihnen","Ihr","Ihre","Ihrem","Ihren","Ihrer","Ihres"}
ABBREV_END = re.compile(r"(z\.\s*B\.|u\.\s*a\.|d\.\s*h\.|bzw\.|etc\.|vgl\.|ca\.|bspw\.)\s*$", re.IGNORECASE)

LOWER = "a-zäöüß"
UPPER = "A-ZÄÖÜ"

# ---------- LaTeX-Bereinigung & Vorverarbeitung ----------

def strip_comments(line: str) -> str:
    out, esc = [], False
    for ch in line:
        if ch == "\\":
            esc = not esc
            out.append(ch)
            continue
        if ch == "%" and not esc:
            break
        esc = False
        out.append(ch)
    return "".join(out)

def remove_special_quoted(text: str) -> str:
    # Entfernt alles zwischen \enquote{ ... } (deine speziellen Anführungszeichen)
    # non-greedy, mehrfache Vorkommen pro Zeile
    return re.sub(r'\\\enquote{.*?\\}', " ", text)

def strip_latex(text: str) -> str:
    text = remove_special_quoted(text)
    # Math
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\\([^\)]*\\\)", " ", text)
    text = re.sub(r"\\\[[^\]]*\\\]", " ", text)
    # Kommandos
    text = re.sub(r"\\[A-Za-z@]+(\s*\[[^\]]*\])*(\s*\{[^{}]*\})*", " ", text)
    # Mehrfach-Whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ---------- Sprach-/Wortheuristiken ----------

def is_german_like_word(token_text: str) -> bool:
    """Deutsch-Heuristik:
    - ignoriere IGNORE_WORDS & reine Akronyme
    - vergleiche wordfreq: de_zipf >= 2.5 und de_zipf >= en_zipf + 0.5 (deutlich deutscher als englisch)
      oder en_zipf < 2.0 (englisch selten -> lass als potenziell deutsch durch)
    """
    w = token_text.strip("-")
    if not w:
        return False
    wl = w.lower()
    if wl in IGNORE_WORDS:
        return False
    if w.isupper() and len(w) > 1:
        return False

    # Hyphen: aufteilen und die beste Einschätzung nehmen
    parts = [p for p in re.split(r"[-‑–—]", w) if p]
    de_scores, en_scores = [], []
    for p in parts:
        de_scores.append(zipf_frequency(p.lower(), "de"))
        en_scores.append(zipf_frequency(p.lower(), "en"))

    de = max(de_scores) if de_scores else 0.0
    en = max(en_scores) if en_scores else 0.0

    if de >= 2.5 and (de >= en + 0.5 or en < 2.0):
        return True
    return False

def first_is_lower(txt: str) -> bool:
    return bool(re.match(rf"^[{LOWER}]", txt))

def first_is_upper(txt: str) -> bool:
    return bool(re.match(rf"^[{UPPER}]", txt))

# ---------- Kernprüfung ----------

def check_line(clean_line: str, line_begins_new_sentence: bool):
    """Gibt Liste von (word, reason) zurück.
    - Satzanfang nur prüfen, wenn line_begins_new_sentence == True
    - Innerhalb der Zeile weiterhin .?!-basierte Satzanfänge prüfen
    """
    issues = []
    if not clean_line:
        return issues

    doc = nlp(clean_line)

    # Prüfen, ob am Zeilenanfang ein (neuer) Satz beginnt, abhängig von vorheriger Zeile.
    # Wir benutzen spaCy-Sätze, prüfen aber explizit den ersten Token des ersten Satzes nur,
    # wenn line_begins_new_sentence == True.
    for si, sent in enumerate(doc.sents):
        # ob vor diesem Satz eine Abkürzung steht (nur relevant, wenn nicht am Zeilenanfang)
        sent_text_before = clean_line[:sent.start_char]
        abbrev_before = bool(ABBREV_END.search(sent_text_before)) if sent.start_char > 0 else False

        for i, tok in enumerate(sent):
            if not tok.is_alpha:
                continue
            w = tok.text

            # Englisch/Namen/Fremdwort filtern
            if not is_german_like_word(w):
                continue

            is_first_token_in_sent = (i == 0)

            # a) Satzanfang am wirklichen Zeilenanfang: nur prüfen, wenn die vorige Zeile endete.
            if si == 0 and is_first_token_in_sent:
                if line_begins_new_sentence and not abbrev_before and first_is_lower(w):
                    issues.append((w, "satzanfang_klein"))
                # danach normal weiter zu b/c
                continue

            # b) Satzanfang innerhalb der Zeile nach .?! (spaCy-Segmentierung)
            if is_first_token_in_sent and sent.start_char > 0 and not abbrev_before and first_is_lower(w):
                issues.append((w, "satzanfang_klein"))
                continue

            # c) In Satzmitte: Nomen klein?
            if not is_first_token_in_sent:
                if tok.pos_ == "NOUN" and first_is_lower(w):
                    issues.append((w, "nomen_klein"))
                    continue
                # d) Nicht-Nomen unnötig groß? (Höflichkeitspronomen erlauben)
                if tok.pos_ != "NOUN" and first_is_upper(w) and w not in FORMAL_PRONOUNS:
                    # Eigennamen (PROPN) ignorieren
                    if tok.pos_ != "PROPN":
                        issues.append((w, "unnötig_groß"))
                        continue
    return issues

# ---------- Hauptprogramm ----------

def main():
    findings = defaultdict(list)  # file -> [(line_no, word, reason)]
    for fname in sorted(os.listdir(".")):
        if not fname.endswith(TEX_EXT) or fname in EXCLUDE_FILES:
            continue

        prev_clean = ""  # bereinigte vorherige Zeile
        with open(fname, "r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                no_comment = strip_comments(raw.rstrip("\n"))
                if not no_comment.strip():
                    prev_clean = ""
                    continue

                clean = strip_latex(no_comment)
                clean = clean.strip()

                if not clean:
                    prev_clean = ""
                    continue

                # (1) Nur wenn vorige bereinigte Zeile mit .?! endet, gilt der ANFANG dieser Zeile als Satzanfang
                begins_new_sentence = bool(re.search(r"[.!?]\s*$", prev_clean)) if prev_clean else False

                for (word, reason) in check_line(clean, begins_new_sentence):
                    findings[fname].append((lineno, word, reason))

                prev_clean = clean

    # Ausgabe sortiert: Datei -> Zeile
    rows = []
    for fname in sorted(findings.keys()):
        for lineno, word, _reason in sorted(findings[fname], key=lambda x: x[0]):
            rows.append((fname, lineno, word))

    if not rows:
        print("✅ Keine problematische Groß-/Kleinschreibung deutscher Wörter gefunden.")
        return

    col1 = max(len("Datei"), max(len(r[0]) for r in rows))
    col2 = max(len("Zeile"), max(len(str(r[1])) for r in rows))
    col3 = max(len("Wort"), max(len(r[2]) for r in rows))

    print(f"{'Datei'.ljust(col1)}  {'Zeile'.rjust(col2)}  {'Wort'.ljust(col3)}")
    print("-" * (col1 + col2 + col3 + 4))
    for fname, line, word in rows:
        print(f"{fname.ljust(col1)}  {str(line).rjust(col2)}  {word.ljust(col3)}")

    print("\nℹ️  Regeln: Satzanfang groß (nur wenn vorherige Zeile mit .?! endete); Nomen in Satzmitte groß;")
    print("   Nicht‑Nomen in Satzmitte klein. Englische Wörter werden herausgefiltert.")
    print("   Inhalte zwischen \\(\"\\) ... \\(\"\\) werden ignoriert.")

if __name__ == "__main__":
    main()
