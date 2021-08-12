all:	manual.pdf

clean:
	rm -f *.aux *.log *.out *.toc manual-body.tex

manual-body.tex: manual.md
	multimarkdown manual.md -t latex -o manual-body.tex
	sed -i -e 's/{verbatim}/{code}/g' -e 's/\[htbp\]/\[h!\]/g' -e '/end{figure}/a \\\FloatBarrier' manual-body.tex

manual.pdf: manual-body.tex manual.tex
	xelatex manual.tex
	xelatex manual.tex
	xelatex manual.tex
