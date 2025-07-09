import os
import re
from collections import Counter

def count_words_in_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()
    # Remove LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+\{[^}]*}", "", text)
    text = re.sub(r"%.*", "", text)

    words = re.findall(r"\b\w+\b", text)
    characters = re.findall(r"\w", text)
    return len(words), len(characters), words


def count_most_common_words(section_counts):
    word_counter = Counter()
    for section_file in section_counts.keys():
        _, _, words = count_words_in_file(section_file)
        # Normalize to lowercase
        words = [word.lower() for word in words]
        word_counter.update(words)

    fuellwoerter = {
        # Artikel, Pronomen, Hilfsverben, Konjunktionen, Präpositionen, Modalverben, Adverbien
        "der", "die", "das", "ein", "eine", "einer", "eines", "einem", "einen",
        "und", "oder", "zu", "mit", "von", "für", "auf", "in", "an", "dem", "den",
        "des", "dass", "da", "damit", "so", "doch", "als", "bei", "wird", "werden",
        "ist", "sind", "nicht", "auch", "wie", "man", "es", "am", "im", "noch",
        "zum", "aus", "durch", "welche", "wenn", "wurde", "wird", "dadurch",
        "dies", "diese", "dieser", "dieses", "sich", "kann", "können", "gibt",
        "jedoch", "um", "sie", "haben", "hat", "dabei", "bestimmte",
        "einig", "mehr", "nur", "schon", "etwa", "etwas", "oft", "immer", "alle",
        "viele", "wenige", "sehr", "ab", "über", "unter", "zwischen", "gegen",
        "ohne", "wegen", "trotz", "nach", "vor", "seit", "bis", "hin",
        "anhand", "laut", "mithilfe", "unter anderem", "beim", "zur", "anderen", "erkennen", "zudem",
        "somit", "wurden", "er", "ich", "sie"
    }

    # Separate Füllwörter and normal words
    fuell_counter = Counter()
    normal_counter = Counter()
    for word, count in word_counter.items():
        if word in fuellwoerter:
            fuell_counter[word] = count
        else:
            normal_counter[word] = count

    print("\n25 meistgenutzte Füllwörter (über alle Sektionen hinweg):")
    print("-" * 40)
    for word, count in fuell_counter.most_common(25):
        print(f"{word:<15}{count}")
    print("-" * 40)

    print("25 meistgenutzte normale Wörter (über alle Sektionen hinweg):")
    print("-" * 40)
    for word, count in normal_counter.most_common(25):
        print(f"{word:<15}{count}")
    print("-" * 40)


def main():
    main_file = "main.tex"
    total_words = 0
    total_characters = 0
    section_counts = {}

    with open(main_file, "r", encoding="utf-8") as f:
        main_text = [line.lstrip() for line in f.readlines() if line.strip()]

    for line in main_text:
        match = re.match(r"\\input{(.+)}", line)
        if match:
            section_file = match.group(1).strip() + ".tex"
            if os.path.exists(section_file):
                words, characters, _ = count_words_in_file(section_file)
                section_counts[section_file] = [words, characters]
                total_words += words
                total_characters += characters

    print(f"{'Sektion':<20}{'Wörter':<10}{'Zeichen':<10}")
    print("-" * 40)
    for section, count in section_counts.items():
        name = section.replace(".tex", "").capitalize()
        print(f"{name:<20}{count[0]:<10}{count[1]:<10}")
    print("-" * 40)
    print(f"{'Alle':<20}{total_words:<10}{total_characters:<10}")

    # Häufigste Wörter ausgeben
    count_most_common_words(section_counts)


if __name__ == "__main__":
    main()
