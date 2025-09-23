# check_de_caps.py
# Prüft Groß-/Kleinschreibung deutscher Wörter in .tex-Dateien – mit Ausnahmen für deine False Positives.

import os
import re
import sys
from collections import defaultdict

try:
    import spacy
    from wordfreq import zipf_frequency
except ImportError:
    print(
        "Bitte installiere Abhängigkeiten:\n  python -m pip install -U spacy wordfreq\n  python -m spacy download de_core_news_sm"
    )
    sys.exit(1)

# spaCy laden
try:
    nlp = spacy.load("de_core_news_sm")
except OSError:
    print("spaCy-Modell 'de_core_news_sm' fehlt.\nInstalliere mit:\n  python -m spacy download de_core_news_sm")
    sys.exit(1)

EXCLUDE_FILES = {"main.tex", "titlepage.tex"}
TEX_EXT = ".tex"

LOWER = "a-zäöüß"
UPPER = "A-ZÄÖÜ"

# --- Whitelists & Phrasen, die NICHT geflaggt werden sollen ---
IGNORE_WORDS = {
    # deine Tech-/Acronym-Liste
    "amt", "cnn", "rnn", "lstm", "gru", "mlp", "mt3", "yourmt3", "omnizart", "mfcc", "cqt",
    "json", "csv", "midi", "xml", "yaml", "wav", "fps", "ui", "vr", "ros", "ros2", "rssi", "dbm", "gpu", "cpu",
    # zusätzlich problematische Fälle
    "künstlicher", "künstliche", "künstliches", "künstlichen", "künstlichem",  # Flexionen
    "vielseitiger", "robuster", "schwerer", "können",
    # Funktionswörter, die fälschlich als satzanfang_klein auftauchten und du nicht markiert haben willst:
    "die", "wie",
    # häufige Lemmas, die je nach Kontext falsch getaggt werden:
    "mithilfe", "verwirren", "muss"
}
FORMAL_PRONOUNS = {"Sie", "Ihnen", "Ihr", "Ihre", "Ihrem", "Ihren", "Ihrer", "Ihres"}
ABBREV_END = re.compile(r"(z\.\s*B\.|u\.\s*a\.|d\.\s*h\.|bzw\.|etc\.|vgl\.|ca\.|bspw\.)\s*$", re.IGNORECASE)

# Feste Wortgruppe: Künstliche(r/…) Intelligenz (Großschreibung des ersten Wortes akzeptieren)
KI_PHRASE = re.compile(r"^künstlich(?:e|er|es|en|em)?$", re.IGNORECASE)


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
    # Entfernt \enquote{...} (einfacher Fall, keine geschachtelten Klammern)
    out = re.sub(r'\\enquote\{[^{}]*\}', ' ', text, flags=re.DOTALL)
    return re.sub(r'\s{2,}', ' ', out).strip()


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
    parts = [p for p in re.split(r"[--–—]", w) if p]
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


# ---------- Hilfen für Kontext-Checks ----------

def is_token_after_colon(doc, tok) -> bool:
    """Ist dies der erste alphabetische Token nach einem ':' in seinem Satz?"""
    sent = tok.sent
    # finde das ':' vor tok
    colon_idx = None
    for i, t in enumerate(sent):
        if t.text == ":":
            colon_idx = i
        if t.i == tok.i:
            break
    if colon_idx is None:
        return False
    # erster alphabetischer Token nach ':' ?
    for j in range(colon_idx + 1, len(sent)):
        if sent[j].is_alpha:
            return sent[j].i == tok.i
    return False


def line_has_item(raw_line: str) -> bool:
    return "\\item" in raw_line


# ---------- Kernprüfung ----------

def check_line(clean_line: str, raw_line: str, line_begins_new_sentence: bool):
    r"""Gibt Liste von (word, reason) zurück (reduziert False Positives).
    - Satzanfang nur prüfen, wenn line_begins_new_sentence == True
    - Innerhalb der Zeile weiterhin .?!-basierte Satzanfänge prüfen
    - Nach ':' gilt der erste Token als neuer (untergeordneter) Satzanfang → Groß erlaubt
    - In \item-Zeilen wird Großschreibung nach ':' generell toleriert
    - KI-Phrase ('Künstliche Intelligenz' inkl. Flexionen) niemals flaggen
    - Sonderfälle 'die', 'wie' am (vermeintlichen) Satzanfang nicht flaggen
    """
    issues = []
    if not clean_line:
        return issues

    doc = nlp(clean_line)
    in_item = line_has_item(raw_line)

    for si, sent in enumerate(doc.sents):
        sent_text_before = clean_line[:sent.start_char]
        abbrev_before = bool(ABBREV_END.search(sent_text_before)) if sent.start_char > 0 else False

        for i, tok in enumerate(sent):
            if not tok.is_alpha:
                continue

            w = tok.text
            wl = w.lower()

            # Harte Whitelist / feste Phrasen
            if wl in IGNORE_WORDS:
                continue
            # Künstliche(r/…) Intelligenz – ignoriere den ersten Teil der Phrase
            if KI_PHRASE.match(w) and (tok.nbor(1).text.lower() if tok.i + 1 < len(doc) else "") == "intelligenz":
                continue

            # Englisch/Namen/Fremdwort filtern
            if not is_german_like_word(w):
                continue

            is_first_token_in_sent = (i == 0)

            # Ausnahme: nach ':' gilt erstes Wort als (untergeordneter) Satzanfang → Groß erlaubt
            after_colon = is_token_after_colon(doc, tok)
            if after_colon:
                # kein satzanfang_klein und kein unnötig_groß nach ':'
                continue

            # Ausnahme: \item-Zeilen – toleranter (Listenstil)
            if in_item:
                # Ersten alphabetischen Token in der Zeile großzügig behandeln
                # (keine Flags für Großschreibung am Anfang/gleich nach Formatierung)
                if is_first_token_in_sent or w[0].isupper():
                    continue

            # a) Satzanfang am wirklichen Zeilenanfang
            if si == 0 and is_first_token_in_sent:
                if line_begins_new_sentence and not abbrev_before:
                    # Deine Sonderfälle „die“, „wie“ nicht markieren
                    if wl in {"die", "wie"}:
                        pass
                    elif first_is_lower(w):
                        issues.append((w, "satzanfang_klein"))
                continue

            # b) Satzanfang innerhalb der Zeile nach .?! (spaCy-Segmentierung)
            if is_first_token_in_sent and sent.start_char > 0 and not abbrev_before and first_is_lower(w):
                # Sonderfälle „die“, „wie“ hier ebenfalls nicht markieren
                if wl not in {"die", "wie"}:
                    issues.append((w, "satzanfang_klein"))
                continue

            # c) In Satzmitte: Nomen klein?
            if not is_first_token_in_sent:
                if tok.pos_ == "NOUN" and first_is_lower(w):
                    # zähle nur echte Nomen – spaCy ist hier manchmal unsicher;
                    # wenn das Wort auf typische Adjektiv-Endungen endet, NICHT als Nomen behandeln
                    if not re.search(r"(e|er|es|en|em)$", wl):
                        issues.append((w, "nomen_klein"))
                    continue
                # d) Nicht-Nomen unnötig groß? (Höflichkeitspronomen erlauben)
                if tok.pos_ != "NOUN" and first_is_upper(w) and w not in FORMAL_PRONOUNS:
                    # Eigennamen (PROPN) ignorieren
                    if tok.pos_ != "PROPN":
                        # nach ':' bereits oben ausgenommen; zusätzlich: lasse Großschreibung nach Item-Labels zu
                        if not in_item:
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
        prev_raw_nonempty = ""  # letzte nicht-leere Raw-Zeile (für Kontext wie \item)
        with open(fname, "r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                no_comment = strip_comments(raw.rstrip("\n"))
                if not no_comment.strip():
                    prev_clean = ""
                    continue

                clean = strip_latex(no_comment).strip()
                if not clean:
                    prev_clean = ""
                    continue

                # (1) Nur wenn vorige bereinigte Zeile mit .?! endet, gilt der ANFANG dieser Zeile als Satzanfang
                begins_new_sentence = bool(re.search(r"[.!?]\s*$", prev_clean)) if prev_clean else False

                for (word, reason) in check_line(clean, no_comment, begins_new_sentence):
                    findings[fname].append((lineno, word, reason))

                prev_clean = clean
                prev_raw_nonempty = no_comment

    # Ausgabe sortiert: Datei -> Zeile
    rows = []
    for fname in sorted(findings.keys()):
        for lineno, word, reason in sorted(findings[fname], key=lambda x: x[0]):
            rows.append((fname, lineno, word, reason))

    if not rows:
        print("✅ Keine problematische Groß-/Kleinschreibung deutscher Wörter gefunden.")
        return

    col1 = max(len("Datei"), max(len(r[0]) for r in rows))
    col2 = max(len("Zeile"), max(len(str(r[1])) for r in rows))
    col3 = max(len("Wort"), max(len(r[2]) for r in rows))
    col4 = max(len("Grund"), max(len(r[3]) for r in rows))

    print(f"{'Datei'.ljust(col1)}  {'Zeile'.rjust(col2)}  {'Wort'.ljust(col3)}  {'Grund'.ljust(col4)}")
    print("-" * (col1 + col2 + col3 + col4 + 6))
    for fname, line, word, reason in rows:
        print(f"{fname.ljust(col1)}  {str(line).rjust(col2)}  {word.ljust(col3)}  {reason.ljust(col4)}")

    print("\nℹ️ Regeln:")
    print("   • Satzanfang groß (nur wenn vorherige Zeile mit .?! endete).")
    print("   • Nach ':' gilt der erste Token als neuer Satzbeginn → Groß erlaubt.")
    print("   • In \\item-Zeilen Großschreibung großzügiger behandeln.")
    print("   • Nomen in Satzmitte groß; Nicht-Nomen in Satzmitte klein (außer Eigennamen/Höflichkeitspronomen).")
    print("   • Feste Phrase 'Künstliche(r/…) Intelligenz' nicht markieren.")
    print("   • Sonderfälle 'die', 'wie' am (vermeintlichen) Satzanfang nicht markieren.")
    print("   • Englische Wörter werden herausgefiltert; Inhalte in \\enquote{...} ignoriert.")


if __name__ == "__main__":
    main()
