@echo off
mkdir auxil 2>nul
mkdir out 2>nul

pdflatex -interaction=nonstopmode -output-directory=out -aux-directory=auxil main.tex
biber --input-directory=auxil --output-directory=out main
pdflatex -interaction=nonstopmode -output-directory=out -aux-directory=auxil main.tex
pdflatex -interaction=nonstopmode -output-directory=out -aux-directory=auxil main.tex
python wordcount.py