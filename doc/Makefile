all:	reinstead.pdf

clean:
	rm -f *.aux *.log *.out *.toc manual-body.tex

manual-body.tex: manual.md
	multimarkdown manual.md -t latex -o manual-body.tex
	sed -i -e 's/{verbatim}/{code}/g' -e 's/\[htbp\]/\[h!\]/g' -e '/end{figure}/a \\\FloatBarrier' manual-body.tex

reinstead.pdf: manual-body.tex manual.tex preamble.tex
	xelatex -jobname=reinstead manual.tex
	xelatex -jobname=reinstead manual.tex
	xelatex -jobname=reinstead manual.tex
