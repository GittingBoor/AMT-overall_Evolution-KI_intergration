import os
import re

def count_words_in_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()
    # Remove LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", text)
    text = re.sub(r"%.*", "", text)

    words = re.findall(r"\b\w+\b", text)
    characters = re.findall(r"\w", text)
    return len(words), len(characters)


def main():
    main_file = "praxissemesterbericht.tex"
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
                words, characters = count_words_in_file(section_file)
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


if __name__ == "__main__":
    main()