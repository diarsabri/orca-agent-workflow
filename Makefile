.PHONY: test check demo

test:
	python3 -m unittest discover -s tests -q

check: test
	python3 .agents/workflow.py check
	python3 scripts/check_docs.py
	python3 scripts/scan_public.py

demo:
	python3 examples/offline_demo.py
