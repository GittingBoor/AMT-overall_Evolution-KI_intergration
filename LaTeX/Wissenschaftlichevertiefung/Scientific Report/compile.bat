@echo off
mkdir auxil 2>nul
mkdir out 2>nul

pdflatex -interaction=nonstopmode -output-directory=out -aux-directory=auxil praxissemesterbericht.tex
biber --input-directory=auxil --output-directory=out praxissemesterbericht
pdflatex -interaction=nonstopmode -output-directory=out -aux-directory=auxil praxissemesterbericht.tex
pdflatex -interaction=nonstopmode -output-directory=out -aux-directory=auxil praxissemesterbericht.tex
python wordcount.py